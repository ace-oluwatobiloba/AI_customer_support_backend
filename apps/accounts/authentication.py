"""
Custom JWT authentication enforcing application account eligibility.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import User


class EligibleAccountJWTAuthentication(JWTAuthentication):
    """
    Authenticate JWT requests only for active, verified accounts.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        if (
            not user.is_active
            or user.status != User.Status.ACTIVE
            or not user.email_verified
        ):
            raise AuthenticationFailed(
                "Your account is not permitted to access this resource.",
                code="account_not_eligible",
            )

        return user