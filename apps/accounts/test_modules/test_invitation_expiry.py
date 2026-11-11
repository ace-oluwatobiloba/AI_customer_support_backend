from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import EmployeeInvitation, User
from apps.accounts.services.invitation_expiry import expire_employee_invitations


class EmployeeInvitationExpiryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="expiry-admin@example.com",
            password="AdminPass123!",
        )

    def make_invitation(self, *, email, status, expires_at):
        # Unique token hashes and employee codes are required by the model.
        import hashlib

        token_hash = hashlib.sha256(email.encode()).hexdigest()
        return EmployeeInvitation.objects.create(
            email=email,
            invited_by=self.admin,
            employee_code=f"EXP-{email.split('@')[0]}",
            department="Support",
            token_hash=token_hash,
            status=status,
            expires_at=expires_at,
        )

    def test_expiry_service_marks_only_overdue_pending_invitations(self):
        now = timezone.now()
        expired_pending = self.make_invitation(
            email="overdue@example.com",
            status=EmployeeInvitation.Status.PENDING,
            expires_at=now - timedelta(seconds=1),
        )
        valid_pending = self.make_invitation(
            email="valid@example.com",
            status=EmployeeInvitation.Status.PENDING,
            expires_at=now + timedelta(hours=1),
        )
        accepted = self.make_invitation(
            email="accepted@example.com",
            status=EmployeeInvitation.Status.ACCEPTED,
            expires_at=now - timedelta(days=1),
        )
        revoked = self.make_invitation(
            email="revoked@example.com",
            status=EmployeeInvitation.Status.REVOKED,
            expires_at=now - timedelta(days=1),
        )

        changed = expire_employee_invitations(now=now)

        self.assertEqual(changed, 1)
        expired_pending.refresh_from_db()
        valid_pending.refresh_from_db()
        accepted.refresh_from_db()
        revoked.refresh_from_db()

        self.assertEqual(expired_pending.status, EmployeeInvitation.Status.EXPIRED)
        self.assertEqual(valid_pending.status, EmployeeInvitation.Status.PENDING)
        self.assertEqual(accepted.status, EmployeeInvitation.Status.ACCEPTED)
        self.assertEqual(revoked.status, EmployeeInvitation.Status.REVOKED)

    def test_expiry_service_is_idempotent(self):
        invitation = self.make_invitation(
            email="idempotent@example.com",
            status=EmployeeInvitation.Status.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(expire_employee_invitations(), 1)
        self.assertEqual(expire_employee_invitations(), 0)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, EmployeeInvitation.Status.EXPIRED)

    def test_management_command_reports_expired_count(self):
        self.make_invitation(
            email="command@example.com",
            status=EmployeeInvitation.Status.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        output = StringIO()

        call_command("expire_employee_invitations", stdout=output)

        self.assertIn("Expired 1 employee invitation(s).", output.getvalue())
