"""Cross-component integration tests for support, audit, and notifications.

These tests exercise the transactional boundary between ticket assignment,
centralized audit recording, in-app notification persistence, and Resend
delivery callbacks. External email delivery is always mocked.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.notifications.models import Notification, NotificationDelivery
from apps.support.models import Ticket, TicketAssignment
from apps.support.services import auto_assign_ticket


User = get_user_model()


class SupportAuditNotificationIntegrationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="stage6-customer@example.com",
            password="Stage6-Customer-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )
        self.agent = User.objects.create_user(
            email="stage6-agent@example.com",
            password="Stage6-Agent-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )
        self.ticket = Ticket.objects.create(
            ticket_number="TKT-STAGE6-0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Stage 6 integration ticket",
            description="Ticket for cross-component integration testing.",
            category=Ticket.Category.OTHER,
            status=Ticket.Status.OPEN,
        )

    @patch(
        "apps.notifications.services.notification_service.send_mail",
        return_value=1,
    )
    def test_auto_assignment_commits_assignment_audit_notification_and_email(
        self,
        mocked_send_mail,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            assignment = auto_assign_ticket(ticket_id=self.ticket.pk)

        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.ticket_id, self.ticket.pk)
        self.assertEqual(assignment.agent_id, self.agent.pk)

        self.assertTrue(
            TicketAssignment.objects.filter(
                pk=assignment.pk,
                unassigned_at__isnull=True,
            ).exists()
        )

        audit_event = AuditLog.objects.get(
            action="TICKET_AUTO_ASSIGNED",
            entity_id=self.ticket.pk,
        )
        self.assertIsNone(audit_event.actor)
        self.assertEqual(
            audit_event.metadata["assignment_id"],
            str(assignment.pk),
        )
        self.assertEqual(
            audit_event.metadata["agent_id"],
            str(self.agent.pk),
        )

        notification = Notification.objects.get(
            user=self.agent,
            notification_type=Notification.Type.TICKET_ASSIGNED,
        )
        self.assertIn(self.ticket.ticket_number, notification.message)

        delivery = notification.deliveries.get(
            channel=NotificationDelivery.Channel.EMAIL,
        )
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.sent_at)
        mocked_send_mail.assert_called_once()

    @patch(
        "apps.notifications.services.notification_service.send_mail",
        side_effect=RuntimeError("Simulated Resend outage"),
    )
    def test_email_failure_does_not_undo_assignment_audit_or_notification(
        self,
        mocked_send_mail,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            assignment = auto_assign_ticket(ticket_id=self.ticket.pk)

        self.assertIsNotNone(assignment)
        self.assertTrue(
            TicketAssignment.objects.filter(pk=assignment.pk).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action="TICKET_AUTO_ASSIGNED",
                entity_id=self.ticket.pk,
            ).exists()
        )

        notification = Notification.objects.get(
            user=self.agent,
            notification_type=Notification.Type.TICKET_ASSIGNED,
        )
        delivery = notification.deliveries.get()

        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(
            delivery.error_message,
            "Email provider did not accept the message.",
        )
        mocked_send_mail.assert_called_once()

    @patch(
        "apps.support.services.record_audit_event",
        side_effect=RuntimeError("Simulated audit persistence failure"),
    )
    @patch(
        "apps.notifications.services.notification_service.send_mail",
    )
    def test_audit_failure_rolls_back_assignment_and_notification(
        self,
        mocked_send_mail,
        mocked_record_audit_event,
    ):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(
                RuntimeError,
                "Simulated audit persistence failure",
            ):
                auto_assign_ticket(ticket_id=self.ticket.pk)

        self.assertFalse(
            TicketAssignment.objects.filter(ticket=self.ticket).exists()
        )
        self.assertFalse(
            Notification.objects.filter(user=self.agent).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(entity_id=self.ticket.pk).exists()
        )
        mocked_record_audit_event.assert_called_once()
        mocked_send_mail.assert_not_called()
