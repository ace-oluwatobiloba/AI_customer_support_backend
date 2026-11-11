"""Signed email-verification tokens and transactional delivery."""

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services.email_delivery import send_mail, EmailDeliveryError


TOKEN_SALT = "accounts.email-verification"
TOKEN_MAX_AGE = 60 * 60 * 24


class EmailVerificationError(Exception):
    """Raised when email verification cannot be completed."""


def generate_verification_token(user):
    return signing.dumps(
        {"user_id": str(user.pk), "email": user.email},
        salt=TOKEN_SALT,
        compress=True,
    )


def verify_email_token(token):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise EmailVerificationError(
            "The verification token has expired."
        ) from exc
    except signing.BadSignature as exc:
        raise EmailVerificationError(
            "The verification token is invalid."
        ) from exc

    try:
        user = User.objects.get(pk=payload.get("user_id"),
                                email=payload.get("email"))
    except (User.DoesNotExist, ValueError, TypeError) as exc:
        raise EmailVerificationError(
            "The verification token is invalid."
        ) from exc

    if user.email_verified:
        raise EmailVerificationError(
            "This email address has already been verified."
        )
    if not user.is_active or user.status != User.Status.ACTIVE:
        raise EmailVerificationError("This account cannot be verified.")

    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified", "email_verified_at"])
    return user


def send_verification_email(user):
    if user.email_verified:
        raise EmailVerificationError(
            "This email address has already been verified."
        )

    token = generate_verification_token(user)
    verification_path = reverse("accounts:verify-email")
    endpoint = f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}{verification_path}"
    subject = "Verify your email address"
    message = (
        f"Hello,\n\nAn account was created using {user.email}.\n\n"
        f"Submit a POST request to {endpoint} with this JSON body:\n"
        f'{{"token": "{token}"}}\n\n'
        "This verification token expires in 24 hours.\n\n"
        "If you did not request this account, you can ignore this email."
    )
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except EmailDeliveryError as exc:
        raise EmailVerificationError(
            "The verification email could not be sent."
        ) from exc
    if sent_count != 1:
        raise EmailVerificationError("The verification email could not be sent.")
