import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog

User = get_user_model()


class AuditLogModelTests(TestCase):
    """Tests for creating and managing audit log records."""

    def setUp(self):
        # Create a user to act as the audit event actor.
        self.user = User.objects.create_user(
            email="audit-test@example.com",
            password="TestPassword!123",
        )

    def test_audit_log_creation(self):
        # Verify an audit log can be created with its required fields.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="TICKET_CREATED",
            entity_type="Ticket",
            entity_id=uuid.uuid4(),
        )

        self.assertIsInstance(audit_log.id, uuid.UUID)
        self.assertEqual(audit_log.actor, self.user)
        self.assertEqual(audit_log.action, "TICKET_CREATED")
        self.assertEqual(audit_log.entity_type, "Ticket")
        self.assertIsNotNone(audit_log.entity_id)

    def test_audit_log_creation_timestamp(self):
        # Verify Django automatically records when the event was created.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="USER_LOGIN",
            entity_type="User",
        )

        self.assertIsNotNone(audit_log.created_at)

    def test_audit_log_string_representation(self):
        # Verify the model returns its action and entity type as a string.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="TICKET_CREATED",
            entity_type="Ticket",
        )

        self.assertEqual(str(audit_log), "TICKET_CREATED - Ticket")

    def test_audit_log_optional_fields_can_be_null(self):
        # Verify optional fields can be omitted when creating an audit log.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="USER_LOGIN",
            entity_type="User",
        )

        self.assertIsNone(audit_log.entity_id)
        self.assertIsNone(audit_log.metadata)
        self.assertIsNone(audit_log.ip_address)
        self.assertIsNone(audit_log.user_agent)

    def test_audit_log_can_have_metadata(self):
        # Verify additional event details can be stored as JSON metadata.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="TICKET_UPDATED",
            entity_type="Ticket",
            metadata={
                "field": "status",
                "old_value": "OPEN",
                "new_value": "IN_PROGRESS",
            },
        )

        audit_log.refresh_from_db()

        self.assertEqual(audit_log.metadata["field"], "status")
        self.assertEqual(audit_log.metadata["old_value"], "OPEN")
        self.assertEqual(audit_log.metadata["new_value"], "IN_PROGRESS")

    def test_user_can_have_multiple_audit_logs(self):
        # Verify the actor's related manager returns their audit records.
        AuditLog.objects.create(
            actor=self.user,
            action="USER_LOGIN",
            entity_type="User",
        )
        AuditLog.objects.create(
            actor=self.user,
            action="TICKET_CREATED",
            entity_type="Ticket",
        )

        self.assertEqual(self.user.audit_logs.count(), 2)

    def test_audit_logs_are_ordered_newest_first(self):
        # Create two records with distinct timestamps to verify ordering.
        older_log = AuditLog.objects.create(
            actor=self.user,
            action="USER_LOGIN",
            entity_type="User",
        )
        newer_log = AuditLog.objects.create(
            actor=self.user,
            action="TICKET_CREATED",
            entity_type="Ticket",
        )

        # Set distinct timestamps so the ordering assertion is deterministic.
        AuditLog.objects.filter(pk=older_log.pk).update(
            created_at=timezone.now() - timezone.timedelta(minutes=5)
        )
        AuditLog.objects.filter(pk=newer_log.pk).update(
            created_at=timezone.now()
        )

        logs = list(AuditLog.objects.all())

        self.assertEqual(logs[0].pk, newer_log.pk)
        self.assertEqual(logs[1].pk, older_log.pk)

    def test_deleting_user_preserves_audit_log(self):
        # Verify deleting the actor sets the nullable foreign key to NULL.
        audit_log = AuditLog.objects.create(
            actor=self.user,
            action="USER_LOGIN",
            entity_type="User",
        )

        self.user.delete()
        audit_log.refresh_from_db()

        self.assertIsNone(audit_log.actor)
        self.assertEqual(audit_log.action, "USER_LOGIN")