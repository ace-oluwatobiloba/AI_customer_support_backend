"""Mark overdue pending employee invitations as expired."""

from django.core.management.base import BaseCommand

from apps.accounts.services.invitation_expiry import expire_employee_invitations


class Command(BaseCommand):
    help = "Mark pending employee invitations past their expiry time as expired."

    def handle(self, *args, **options):
        count = expire_employee_invitations()
        self.stdout.write(
            self.style.SUCCESS(
                f"Expired {count} employee invitation(s)."
            )
        )
