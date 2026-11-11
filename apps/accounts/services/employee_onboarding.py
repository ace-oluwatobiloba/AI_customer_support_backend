"""Administrator-controlled employee invitation and Agent provisioning."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AgentProfile, EmployeeInvitation, User
from apps.accounts.services.email_delivery import send_mail, EmailDeliveryError
from apps.audit.services import record_audit_event


class EmployeeOnboardingError(Exception):
    """Raised when employee invitation or acceptance cannot be completed."""


class EmployeeInvitationDeliveryError(EmployeeOnboardingError):
    """Invitation was recorded, but the email provider did not accept delivery."""


INVITATION_TTL_HOURS = 72


def _audit(actor, action, invitation, metadata=None):
    """Record employee-onboarding events through the centralized audit service."""
    return record_audit_event(
        actor=actor,
        action=action,
        entity=invitation,
        metadata=metadata or {},
    )


def invite_employee(*, invited_by, email, employee_code, department="",
                    specialization=""):
    """Create an invitation, commit it, then synchronously send its email.

    Sending occurs after the database transaction commits. This prevents a
    provider exception raised during an on_commit callback from becoming an
    unexplained HTTP 500 after the invitation has already been committed.
    """
    if (invited_by.role != User.Role.ADMIN
            or invited_by.status != User.Status.ACTIVE
            or not invited_by.is_active):
        raise EmployeeOnboardingError(
            "Only an active administrator can invite employees."
        )

    email = User.objects.normalize_email(email)
    if User.objects.filter(email__iexact=email).exists():
        raise EmployeeOnboardingError("An account with this email already exists.")
    if EmployeeInvitation.objects.filter(
        email__iexact=email, status=EmployeeInvitation.Status.PENDING
    ).exists():
        raise EmployeeOnboardingError(
            "A pending invitation already exists for this email."
        )
    if AgentProfile.objects.filter(employee_code=employee_code).exists():
        raise EmployeeOnboardingError("This employee code is already in use.")

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    with transaction.atomic():
        invitation = EmployeeInvitation.objects.create(
            email=email,
            invited_by=invited_by,
            employee_code=employee_code,
            department=department or None,
            specialization=specialization or None,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(hours=INVITATION_TTL_HOURS),
        )
        _audit(invited_by, "EMPLOYEE_INVITED", invitation, {"email": email})

    accept_url = (
        f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}"
        f"{reverse('accounts:accept-employee-invitation')}"
    )
    subject = "Invitation to join the customer support team"
    message = (
        "You have been invited to join the customer support team as an agent.\n\n"
        f"Complete your account setup by submitting this invitation token to "
        f"{accept_url}:\n\n{raw_token}\n\n"
        f"This invitation expires in {INVITATION_TTL_HOURS} hours. "
        "If you were not expecting this invitation, ignore this email."
    )
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise EmailDeliveryError("The provider did not accept the message.")
    except EmailDeliveryError as exc:
        # The token was never delivered. Revoke the unusable invitation while
        # preserving the audit trail; a later attempt can issue a fresh token.
        with transaction.atomic():
            invitation.status = EmployeeInvitation.Status.REVOKED
            invitation.save(update_fields=["status"])
            _audit(invited_by, "EMPLOYEE_INVITATION_EMAIL_FAILED", invitation,
                   {"email": email})
        raise EmployeeInvitationDeliveryError(
            "The invitation could not be emailed. No usable invitation remains."
        ) from exc

    return invitation


def accept_employee_invitation(*, token, password, password_confirm):
    """Validate an invitation and provision an active Agent account."""
    if password != password_confirm:
        raise EmployeeOnboardingError("The passwords do not match.")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation_expired = False
    try:
        with transaction.atomic():
            invitation = (
                EmployeeInvitation.objects.select_for_update().get(
                    token_hash=token_hash,
                    status=EmployeeInvitation.Status.PENDING,
                )
            )
            if invitation.expires_at <= timezone.now():
                invitation.status = EmployeeInvitation.Status.EXPIRED
                invitation.save(update_fields=["status"])
                invitation_expired = True
            else:
                validate_password(password)
                if User.objects.filter(email__iexact=invitation.email).exists():
                    raise EmployeeOnboardingError(
                        "An account with this email already exists."
                    )
                user = User.objects.create_user(
                    email=invitation.email,
                    password=password,
                    role=User.Role.AGENT,
                    status=User.Status.ACTIVE,
                    is_active=True,
                    email_verified=True,
                    email_verified_at=timezone.now(),
                )
                AgentProfile.objects.create(
                    user=user,
                    employee_code=invitation.employee_code,
                    department=invitation.department,
                    specialization=invitation.specialization,
                )
                invitation.status = EmployeeInvitation.Status.ACCEPTED
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=["status", "accepted_at"])
                _audit(user, "EMPLOYEE_INVITATION_ACCEPTED", invitation, {
                    "employee_user_id": str(user.pk), "email": user.email,
                })
                return user
    except EmployeeInvitation.DoesNotExist as exc:
        raise EmployeeOnboardingError(
            "This invitation is invalid or has already been used."
        ) from exc

    if invitation_expired:
        raise EmployeeOnboardingError("This invitation has expired.")
