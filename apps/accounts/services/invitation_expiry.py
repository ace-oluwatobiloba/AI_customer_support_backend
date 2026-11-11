"""Services for synchronizing employee invitation expiry state."""

from django.utils import timezone

from apps.accounts.models import EmployeeInvitation


def expire_employee_invitations(*, now=None):
    """Mark all overdue pending employee invitations as expired.

    Returns the number of invitation rows changed. The conditional update makes
    repeated executions safe and leaves accepted/revoked invitations untouched.
    """
    current_time = now or timezone.now()
    return EmployeeInvitation.objects.filter(
        status=EmployeeInvitation.Status.PENDING,
        expires_at__lte=current_time,
    ).update(status=EmployeeInvitation.Status.EXPIRED)
