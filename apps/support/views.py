"""
API views for support ticket management.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.support.models import TicketAssignment
from apps.support.serializers.assignments import (
    TicketAssignmentCreateSerializer,
    TicketAssignmentSerializer,
)
from apps.support.services import (
    TicketAssignmentError,
    assign_ticket,
)

from rest_framework import generics, permissions

from apps.accounts.models import User
from apps.conversations.models import Conversation
from apps.support.models import Ticket, TicketEscalation
from apps.support.serializers.tickets import TicketSerializer
from apps.support.services import create_customer_ticket
from apps.support.permissions import IsAdmin, IsAgent, IsActiveAccount
from apps.support.serializers.escalations import (
    TicketEscalationCreateSerializer,
    TicketEscalationSerializer,
)

from apps.support.services import (
    TicketEscalationError,
    escalate_ticket,
)

class TicketListCreateView(generics.ListCreateAPIView):
    """
    List tickets visible to the current user or create a customer ticket.
    """

    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Never expose tickets to an inactive or suspended account.
        if (
            not user.is_active
            or user.status != User.Status.ACTIVE
        ):
            return Ticket.objects.none()

        if user.role == User.Role.CUSTOMER:
            return Ticket.objects.filter(customer=user)

        if user.role == User.Role.AGENT:
            return Ticket.objects.filter(
                assignments__agent=user,
                assignments__unassigned_at__isnull=True,
            ).distinct()

        if user.role == User.Role.ADMIN:
            return Ticket.objects.all()

        return Ticket.objects.none()

    def create(self, request, *args, **kwargs):
        # Restrict ticket creation to customers for this initial API.
        if request.user.role != User.Role.CUSTOMER:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Only customers may create tickets through this endpoint."
            )

        if (
            not request.user.is_active
            or request.user.status != User.Status.ACTIVE
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "Your account is not permitted to create tickets."
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # The service sets customer identity and server-controlled fields.
        create_customer_ticket(
            customer=self.request.user,
            title=serializer.validated_data["title"],
            description=serializer.validated_data["description"],
            category=serializer.validated_data.get(
                "category",
                Ticket.Category.OTHER,
            ),
        )

class TicketDetailView(generics.RetrieveAPIView):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    lookup_field = "id"
    lookup_url_kwarg = "ticket_id"

    def get_queryset(self):
        user = self.request.user

        if (
            not user.is_active
            or user.status != User.Status.ACTIVE
        ):
            return Ticket.objects.none()

        if user.role == User.Role.CUSTOMER:
            return Ticket.objects.filter(customer=user)

        if user.role == User.Role.AGENT:
            return Ticket.objects.filter(
                assignments__agent=user,
                assignments__unassigned_at__isnull=True,
            ).distinct()

        if user.role == User.Role.ADMIN:
            return Ticket.objects.all()

        return Ticket.objects.none()

class TicketAssignmentListCreateView(generics.GenericAPIView):
    """
    List assignment history or assign/reassign a ticket.

    Only active administrators may access this endpoint.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TicketAssignmentCreateSerializer

    def check_permissions(self, request):
        super().check_permissions(request)

        user = request.user

        if (
            not user.is_active
            or user.status != User.Status.ACTIVE
            or user.role != User.Role.ADMIN
        ):
            raise PermissionDenied(
                "Only active administrators may manage ticket assignments."
            )

    def get_queryset(self):
        return (
            TicketAssignment.objects
            .select_related("ticket", "agent", "assigned_by")
            .order_by("-assigned_at")
        )

    def get(self, request, ticket_id):
        assignments = self.get_queryset().filter(
            ticket_id=ticket_id,
        )

        if not Ticket.objects.filter(id=ticket_id).exists():
            from rest_framework.exceptions import NotFound

            raise NotFound("Ticket not found.")

        serializer = TicketAssignmentSerializer(
            assignments,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request, ticket_id):
        if not Ticket.objects.filter(id=ticket_id).exists():
            raise NotFound("Ticket not found.")

        request_serializer = self.get_serializer(
            data=request.data,
        )
        request_serializer.is_valid(raise_exception=True)

        try:
            assignment = assign_ticket(
                ticket_id=ticket_id,
                agent_id=request_serializer.validated_data["agent_id"],
                assigned_by=request.user,
                reason=request_serializer.validated_data.get(
                    "reason",
                    "",
                ),
            )
        except TicketAssignmentError as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": str(exc)}) from exc

        response_serializer = TicketAssignmentSerializer(assignment)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

class TicketEscalationListCreateView(generics.GenericAPIView):
    """
    Create escalations and retrieve a ticket's escalation history.

    Active agents may access tickets currently assigned to them.
    Active administrators may access any eligible ticket.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsActiveAccount,
    ]

    serializer_class = TicketEscalationCreateSerializer

    def check_permissions(self, request):
        super().check_permissions(request)

        if request.user.role not in (
            User.Role.AGENT,
            User.Role.ADMIN,
        ):
            raise PermissionDenied(
                "Only active agents and administrators may manage escalations."
            )

    def get_ticket(self, ticket_id):
        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist as exc:
            raise NotFound("Ticket not found.") from exc

        user = self.request.user

        if user.role == User.Role.AGENT:
            is_assigned = TicketAssignment.objects.filter(
                ticket=ticket,
                agent=user,
                unassigned_at__isnull=True,
            ).exists()

            if not is_assigned:
                raise NotFound("Ticket not found.")

        return ticket

    def get(self, request, ticket_id):
        ticket = self.get_ticket(ticket_id)

        escalations = (
            TicketEscalation.objects
            .filter(ticket=ticket)
            .select_related("escalated_by", "conversation")
            .order_by("-created_at")
        )

        serializer = TicketEscalationSerializer(
            escalations,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request, ticket_id):
        ticket = self.get_ticket(ticket_id)

        request_serializer = self.get_serializer(
            data=request.data,
        )
        request_serializer.is_valid(raise_exception=True)

        conversation_id = request_serializer.validated_data.get(
            "conversation_id"
        )

        conversation = None

        if conversation_id is not None:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                )
            except Conversation.DoesNotExist as exc:
                raise ValidationError(
                    {
                        "conversation_id":
                            "The requested conversation does not exist."
                    }
                ) from exc

        try:
            escalation = escalate_ticket(
                ticket_id=ticket.id,
                escalated_by=request.user,
                reason=request_serializer.validated_data["reason"],
                trigger=request_serializer.validated_data["trigger"],
                conversation=conversation,
            )
        except TicketEscalationError as exc:
            raise ValidationError(
                {"detail": str(exc)}
            ) from exc

        response_serializer = TicketEscalationSerializer(
            escalation,
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )