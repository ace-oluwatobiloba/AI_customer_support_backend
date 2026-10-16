"""
API views for support ticket management.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions

from apps.accounts.models import User
from apps.support.models import Ticket
from apps.support.serializers.tickets import TicketSerializer
from apps.support.services import create_customer_ticket


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
    """
    Retrieve a ticket only if it is visible to the current user.
    """

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