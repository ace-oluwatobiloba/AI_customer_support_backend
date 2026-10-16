"""
JWT serializers enforcing application account policies.
"""

from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


User = get_user_model()


def ensure_account_can_authenticate(user):
    """
    Enforce the account eligibility policy.

    Users must be active, have ACTIVE application status,
    and have a verified email address.
    """
    if not user.is_active:
        raise serializers.ValidationError(
            {"detail": "This account is inactive."}
        )

    if user.status != User.Status.ACTIVE:
        raise serializers.ValidationError(
            {"detail": "This account is not active."}
        )

    if not user.email_verified:
        raise serializers.ValidationError(
            {
                "detail": (
                    "Email verification is required before login."
                )
            }
        )


class VerifiedEmailTokenObtainPairSerializer(
    TokenObtainPairSerializer
):
    """
    Issue JWT tokens only to eligible, email-verified users.
    """

    def validate(self, attrs):
        data = super().validate(attrs)

        ensure_account_can_authenticate(self.user)

        return data


class EligibleAccountTokenRefreshSerializer(
    TokenRefreshSerializer
):
    """
    Reject refresh attempts from ineligible accounts.
    """

    def validate(self, attrs):
        refresh_value = attrs.get("refresh")

        try:
            refresh_token = RefreshToken(refresh_value)
        except TokenError as exc:
            raise serializers.ValidationError(
                {"detail": "The refresh token is invalid or expired."}
            ) from exc

        user_id_claim = api_settings.USER_ID_CLAIM
        user_id = refresh_token.get(user_id_claim)

        if user_id is None:
            raise serializers.ValidationError(
                {"detail": "The refresh token is invalid."}
            )

        try:
            user = User.objects.get(
                **{
                    api_settings.USER_ID_FIELD: user_id,
                }
            )
        except (User.DoesNotExist, ValueError, TypeError) as exc:
            raise serializers.ValidationError(
                {"detail": "The account associated with this token does not exist."}
            ) from exc

        ensure_account_can_authenticate(user)

        return super().validate(attrs)