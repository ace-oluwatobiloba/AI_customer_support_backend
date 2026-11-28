"""
Account-registration service.
"""

from django.db import transaction

from apps.accounts.models import CustomerProfile, User
from apps.accounts.services.email_verification import (
    EmailVerificationError,
    send_verification_email,
)


class RegistrationError(Exception):
    """Raised when account registration cannot be completed."""


@transaction.atomic
def register_customer(email, password, first_name, last_name):
    """
    Create an unverified customer account and send verification email.

    Public registration cannot assign privileged roles.
    """
    email = User.objects.normalize_email(email)

    if User.objects.filter(email__iexact=email).exists():
        raise RegistrationError(
            "An account with this email address already exists."
        )

    user = User.objects.create_user(
        email=email,
        password=password,
        role=User.Role.CUSTOMER,
        status=User.Status.ACTIVE,
        email_verified=False,
        email_verified_at=None,
    )

    CustomerProfile.objects.create(
        user=user,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )

    try:
        send_verification_email(user)
    except EmailVerificationError as exc:
        # The database transaction will roll back if email delivery fails.
        raise RegistrationError(
            "Registration could not be completed because "
            "the verification email could not be sent."
        ) from exc

    return user