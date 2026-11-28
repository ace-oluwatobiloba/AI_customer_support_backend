"""
HTTP API views for registration, email verification, and JWT authentication.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.accounts.serializers.authentication import (
    EligibleAccountTokenRefreshSerializer,
    VerifiedEmailTokenObtainPairSerializer,
)
from apps.accounts.serializers.registration import (
    CustomerRegistrationSerializer,
    EmailVerificationSerializer,
)
from apps.accounts.services.email_verification import (
    EmailVerificationError,
    verify_email_token,
)
from apps.accounts.services.registration import (
    RegistrationError,
    register_customer,
)


class CustomerRegistrationView(APIView):
    """
    Register a customer and send an email-verification message.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=CustomerRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                description="Customer registered successfully."
            ),
            400: OpenApiResponse(
                description="Registration data failed validation."
            ),
            503: OpenApiResponse(
                description="Registration could not be completed."
            ),
        },
        tags=["Authentication"],
    )

    def post(self, request):
        serializer = CustomerRegistrationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            user = register_customer(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                first_name=serializer.validated_data["first_name"],
                last_name=serializer.validated_data["last_name"],
            )
        except RegistrationError:
            return Response(
                {
                    "detail": (
                        "Registration could not be completed. "
                        "Please try again later."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": (
                    "Registration successful. "
                    "Check your email to verify your account."
                ),
                "user": {
                    "id": str(user.pk),
                    "email": user.email,
                    "role": user.role,
                    "email_verified": user.email_verified,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerificationView(APIView):
    """
    Verify an email address using a signed verification token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=EmailVerificationSerializer,
        responses={
            200: OpenApiResponse(
                description="Email verified successfully."
            ),
            400: OpenApiResponse(
                description="The verification token is invalid or expired."
            ),
        },
        tags=["Authentication"],
    )

    def get(self, request):
        """Verify an emailed token through a browser link."""
        token = request.query_params.get("token", "")
        if not token:
            return HttpResponse(
                "<h1>Verification link is incomplete</h1><p>Request a new verification email or contact support.</p>",
                status=400,
                content_type="text/html; charset=utf-8",
            )
        try:
            user = verify_email_token(token)
        except EmailVerificationError as exc:
            return HttpResponse(
                f"<h1>Email verification unsuccessful</h1><p>{exc}</p>",
                status=400,
                content_type="text/html; charset=utf-8",
            )
        return HttpResponse(
            "<h1>Email verified</h1><p>Your email address is now verified. You can return to the <a href='/chat/'>customer support sign-in page</a>.</p>",
            status=200,
            content_type="text/html; charset=utf-8",
        )

    def post(self, request):
        serializer = EmailVerificationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            user = verify_email_token(
                serializer.validated_data["token"]
            )
        except EmailVerificationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Email verified successfully.",
                "email": user.email,
                "email_verified": user.email_verified,
                "email_verified_at": user.email_verified_at,
            },
            status=status.HTTP_200_OK,
        )


class VerifiedEmailTokenObtainPairView(TokenObtainPairView):
    """
    Obtain JWT tokens after successful credential and policy checks.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = VerifiedEmailTokenObtainPairSerializer


class EligibleAccountTokenRefreshView(TokenRefreshView):
    """
    Refresh JWT tokens only for eligible accounts.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = EligibleAccountTokenRefreshSerializer

from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from apps.accounts.models import AgentProfile, EmployeeInvitation, User
from apps.accounts.serializers.employee_onboarding import (
    EmployeeInvitationCreateSerializer,
    EmployeeInvitationAcceptSerializer,
    AgentManagementSerializer,
    AgentStatusSerializer,
)
from apps.accounts.services.employee_onboarding import (
    EmployeeOnboardingError,
    EmployeeInvitationDeliveryError,
    invite_employee,
    accept_employee_invitation,
)


class ActiveAdministratorPermission:
    """Small reusable guard for administrator-only account operations."""

    @staticmethod
    def check(user):
        if not (
            user.is_authenticated
            and user.role == User.Role.ADMIN
            and user.status == User.Status.ACTIVE
            and user.is_active
        ):
            raise PermissionDenied("Active administrator access is required.")


class EmployeeInvitationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EmployeeInvitationCreateSerializer,
        responses={201: OpenApiResponse(description="Employee invitation created and emailed.")},
        tags=["Employee Management"],
    )
    def post(self, request):
        ActiveAdministratorPermission.check(request.user)
        serializer = EmployeeInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = invite_employee(invited_by=request.user, **serializer.validated_data)
        except EmployeeInvitationDeliveryError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EmployeeOnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"id": str(invitation.pk), "email": invitation.email,
             "employee_code": invitation.employee_code, "status": invitation.status,
             "expires_at": invitation.expires_at},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["Employee Management"])
    def get(self, request):
        ActiveAdministratorPermission.check(request.user)
        invitations = EmployeeInvitation.objects.select_related("invited_by")
        data = [{
            "id": str(item.pk), "email": item.email, "employee_code": item.employee_code,
            "department": item.department, "status": item.status,
            "expires_at": item.expires_at, "created_at": item.created_at,
        } for item in invitations]
        return Response(data)


class EmployeeInvitationAcceptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=EmployeeInvitationAcceptSerializer,
        responses={201: OpenApiResponse(description="Agent account created.")},
        tags=["Employee Management"],
    )
    def post(self, request):
        serializer = EmployeeInvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = accept_employee_invitation(**serializer.validated_data)
        except EmployeeOnboardingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"message": "Employee account activated.",
             "user": {"id": str(user.pk), "email": user.email, "role": user.role,
                      "email_verified": user.email_verified}},
            status=status.HTTP_201_CREATED,
        )


class AgentListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Employee Management"])
    def get(self, request):
        ActiveAdministratorPermission.check(request.user)
        agents = User.objects.filter(role=User.Role.AGENT).select_related("agent_profile")
        return Response(AgentManagementSerializer(agents, many=True).data)


class AgentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AgentStatusSerializer, tags=["Employee Management"])
    def patch(self, request, user_id):
        ActiveAdministratorPermission.check(request.user)
        agent = get_object_or_404(User, pk=user_id, role=User.Role.AGENT)
        serializer = AgentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        agent.status = new_status
        agent.is_active = new_status == User.Status.ACTIVE
        agent.save(update_fields=["status", "is_active", "updated_at"])
        return Response(AgentManagementSerializer(agent).data)
