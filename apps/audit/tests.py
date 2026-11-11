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

class AuditServiceTests(TestCase):
    """Tests for the centralized audit-event service."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="audit-service-test@example.com",
            password="TestPassword!123",
        )

    def test_records_event_from_model_instance(self):
        from apps.audit.services import record_audit_event

        event = record_audit_event(
            actor=self.user,
            action="TEST_EVENT",
            entity=self.user,
            metadata={"source": "unit_test"},
        )

        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.entity_type, "User")
        self.assertEqual(event.entity_id, self.user.pk)
        self.assertEqual(event.metadata, {"source": "unit_test"})

    def test_records_system_event_without_actor_or_entity_id(self):
        from apps.audit.services import record_audit_event

        event = record_audit_event(
            action="SYSTEM_MAINTENANCE_COMPLETED",
            entity_type="System",
        )

        self.assertIsNone(event.actor)
        self.assertEqual(event.entity_type, "System")
        self.assertIsNone(event.entity_id)

    def test_anonymous_actor_is_recorded_as_none(self):
        from django.contrib.auth.models import AnonymousUser
        from apps.audit.services import record_audit_event

        event = record_audit_event(
            actor=AnonymousUser(),
            action="ANONYMOUS_ACTION",
            entity_type="Authentication",
        )

        self.assertIsNone(event.actor)

    def test_captures_request_ip_and_user_agent(self):
        from django.test import RequestFactory
        from apps.audit.services import record_audit_event

        request = RequestFactory().post("/test/")
        request.META["REMOTE_ADDR"] = "192.0.2.10"
        request.META["HTTP_USER_AGENT"] = "AuditServiceTests/1.0"

        event = record_audit_event(
            actor=self.user,
            action="REQUEST_EVENT",
            entity_type="TestResource",
            request=request,
        )

        self.assertEqual(event.ip_address, "192.0.2.10")
        self.assertEqual(event.user_agent, "AuditServiceTests/1.0")

    def test_does_not_trust_forwarded_for_header(self):
        from django.test import RequestFactory
        from apps.audit.services import record_audit_event

        request = RequestFactory().post("/test/")
        request.META["REMOTE_ADDR"] = "192.0.2.10"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.99"

        event = record_audit_event(
            action="PROXY_REQUEST_EVENT",
            entity_type="TestResource",
            request=request,
        )

        self.assertEqual(event.ip_address, "192.0.2.10")

    def test_rejects_non_dictionary_metadata(self):
        from django.core.exceptions import ValidationError
        from apps.audit.services import record_audit_event

        with self.assertRaises(ValidationError):
            record_audit_event(
                action="INVALID_METADATA",
                entity_type="TestResource",
                metadata=["not", "a", "dictionary"],
            )

    def test_rejects_invalid_entity_uuid(self):
        from django.core.exceptions import ValidationError
        from apps.audit.services import record_audit_event

        with self.assertRaises(ValidationError):
            record_audit_event(
                action="INVALID_ENTITY_ID",
                entity_type="TestResource",
                entity_id="not-a-uuid",
            )

    def test_rejects_empty_action_and_entity_type(self):
        from django.core.exceptions import ValidationError
        from apps.audit.services import record_audit_event

        with self.assertRaises(ValidationError):
            record_audit_event(action="  ", entity_type="TestResource")
        with self.assertRaises(ValidationError):
            record_audit_event(action="VALID_ACTION", entity_type="  ")

    def test_rejects_conflicting_entity_arguments(self):
        from django.core.exceptions import ValidationError
        from apps.audit.services import record_audit_event

        with self.assertRaises(ValidationError):
            record_audit_event(
                action="CONFLICTING_ENTITY",
                entity=self.user,
                entity_type="User",
            )

    def test_rejects_unauthenticated_non_anonymous_actor(self):
        from django.core.exceptions import ValidationError
        from apps.audit.services import record_audit_event

        class UnauthenticatedActor:
            is_authenticated = False

        with self.assertRaises(ValidationError):
            record_audit_event(
                actor=UnauthenticatedActor(),
                action="INVALID_ACTOR",
                entity_type="TestResource",
            )
