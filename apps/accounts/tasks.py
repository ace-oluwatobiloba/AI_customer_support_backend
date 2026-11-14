from celery import shared_task
from apps.accounts.services.invitation_expiry import expire_employee_invitations
@shared_task(name="accounts.expire_employee_invitations")
def expire_employee_invitations_task():
    count = expire_employee_invitations()
    return {"expired_count": count}
