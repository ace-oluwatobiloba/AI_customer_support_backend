"""
Email-verification token generation, validation, and delivery.
"""

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User


TOKEN_SALT = "accounts.email-verification"
TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours


class EmailVerificationError(Exception):
    """Raised when email verification cannot be completed."""


def generate_verification_token(user):
    """
    Generate a signed token tied to a specific user.

    The token contains the user's UUID and current email address.
    Changing the email address invalidates a previously issued token.
    """
    return signing.dumps(
        {
            "user_id": str(user.pk),
            "email": user.email,
        },
        salt=TOKEN_SALT,
        compress=True,
    )


def verify_email_token(token):
    """
    Validate a verification token and mark its account as verified.

    Invalid, expired, malformed, and already-used tokens are rejected.
    """
    try:
        payload = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=TOKEN_MAX_AGE,
        )
    except signing.SignatureExpired as exc:
        raise EmailVerificationError(
            "The verification token has expired."
        ) from exc
    except signing.BadSignature as exc:
        raise EmailVerificationError(
            "The verification token is invalid."
        ) from exc

    user_id = payload.get("user_id")
    email = payload.get("email")

    try:
        user = User.objects.get(
            pk=user_id,
            email=email,
        )
    except (User.DoesNotExist, ValueError, TypeError) as exc:
        raise EmailVerificationError(
            "The verification token is invalid."
        ) from exc

    if user.email_verified:
        raise EmailVerificationError(
            "This email address has already been verified."
        )

    if not user.is_active or user.status != User.Status.ACTIVE:
        raise EmailVerificationError(
            "This account cannot be verified."
        )

    user.email_verified = True
    user.email_verified_at = timezone.now()

    user.save(
        update_fields=[
            "email_verified",
            "email_verified_at",
        ]
    )

    return user


def send_verification_email(user):
    """
    Send an email containing the verification token.

    The verification endpoint accepts the token through a POST request.
    """
    if user.email_verified:
        raise EmailVerificationError(
            "This email address has already been verified."
        )

    token = generate_verification_token(user)

    verification_path = reverse("accounts:verify-email")

    verification_endpoint = (
        f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}"
        f"{verification_path}"
    )

    subject = "Verify your email address"

    message = (
        f"Hello,\n\n"
        f"An account was created using {user.email}.\n\n"
        f"To verify your email address, submit a POST request to:\n"
        f"{verification_endpoint}\n\n"
        f"Use the following JSON body:\n"
        f'{{"token": "{token}"}}\n\n'
        f"This verification token expires in 24 hours.\n\n"
        f"If you did not request this account, you can ignore this email."
    )

    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise EmailVerificationError(
            "The verification email could not be sent."
        ) from exc

    if sent_count != 1:
        raise EmailVerificationError(
            "The verification email could not be sent."
        )