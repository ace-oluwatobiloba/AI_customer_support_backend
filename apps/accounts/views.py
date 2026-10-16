"""
HTTP API views for registration, email verification, and JWT authentication.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def post(self, request):
        serializer = CustomerRegistrationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            user = register_customer(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
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