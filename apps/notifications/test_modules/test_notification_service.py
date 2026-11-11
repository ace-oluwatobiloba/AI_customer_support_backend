"""Tests for centralized notification creation and delivery."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.services.notification_service import (
    create_notification,
    create_notifications,
    deliver_notification_email,
)

User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="notification-service@example.com",
            password="Notification-Test-Password-123!",
        )

    def test_create_notification_persists_in_app_notification(self):
        notification = create_notification(
            user=self.user,
            notification_type=Notification.Type.SYSTEM_ALERT,
            title="Service notice",
            message="A service event occurred.",
        )

        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())
        self.assertEqual(notification.user, self.user)
        self.assertFalse(notification.deliveries.exists())

    def test_rejects_invalid_notification_type(self):
        with self.assertRaises(ValidationError):
            create_notification(
                user=self.user,
                notification_type="NOT_A_REAL_TYPE",
                title="Invalid",
                message="Invalid type.",
            )

    def test_rejects_empty_title(self):
        with self.assertRaises(ValidationError):
            create_notification(
                user=self.user,
                notification_type=Notification.Type.SYSTEM_ALERT,
                title=" ",
                message="Message.",
            )

    def test_rejects_empty_message(self):
        with self.assertRaises(ValidationError):
            create_notification(
                user=self.user,
                notification_type=Notification.Type.SYSTEM_ALERT,
                title="Title",
                message=" ",
            )

    def test_rejects_unsaved_or_missing_recipient(self):
        with self.assertRaises(ValidationError):
            create_notification(
                user=None,
                notification_type=Notification.Type.SYSTEM_ALERT,
                title="Title",
                message="Message.",
            )

    def test_email_delivery_is_scheduled_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            notification = create_notification(
                user=self.user,
                notification_type=Notification.Type.TICKET_ASSIGNED,
                title="Assigned",
                message="A ticket was assigned.",
                send_email=True,
            )

        self.assertEqual(len(callbacks), 1)
        delivery = notification.deliveries.get()
        self.assertEqual(delivery.status, NotificationDelivery.Status.PENDING)
        self.assertEqual(delivery.attempt_count, 0)

    @patch(
        "apps.notifications.services.notification_service.send_mail",
        return_value=1,
    )
    def test_successful_email_delivery_updates_delivery_record(self, mocked_send):
        with self.captureOnCommitCallbacks(execute=False):
            notification = create_notification(
                user=self.user,
                notification_type=Notification.Type.TICKET_ASSIGNED,
                title="Assigned",
                message="A ticket was assigned.",
                send_email=True,
            )

        delivery = notification.deliveries.get()
        result = deliver_notification_email(delivery_id=delivery.pk)

        result.refresh_from_db()
        self.assertEqual(result.status, NotificationDelivery.Status.SENT)
        self.assertEqual(result.attempt_count, 1)
        self.assertIsNotNone(result.sent_at)
        mocked_send.assert_called_once()

    @patch(
        "apps.notifications.services.notification_service.send_mail",
        side_effect=Exception("Simulated provider failure"),
    )
    def test_email_failure_does_not_delete_in_app_notification(self, mocked_send):
        with self.captureOnCommitCallbacks(execute=False):
            notification = create_notification(
                user=self.user,
                notification_type=Notification.Type.TICKET_ASSIGNED,
                title="Assigned",
                message="A ticket was assigned.",
                send_email=True,
            )

        delivery = notification.deliveries.get()
        result = deliver_notification_email(delivery_id=delivery.pk)

        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())
        result.refresh_from_db()
        self.assertEqual(result.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(result.attempt_count, 1)
        self.assertIsNotNone(result.failed_at)
        self.assertEqual(
            result.error_message,
            "Email provider did not accept the message.",
        )
        mocked_send.assert_called_once()

    @patch(
        "apps.notifications.services.notification_service.send_mail",
        return_value=1,
    )
    def test_successfully_sent_delivery_is_not_sent_twice(self, mocked_send):
        with self.captureOnCommitCallbacks(execute=False):
            notification = create_notification(
                user=self.user,
                notification_type=Notification.Type.SYSTEM_ALERT,
                title="One-time notice",
                message="Do not send twice.",
                send_email=True,
            )

        delivery = notification.deliveries.get()
        deliver_notification_email(delivery_id=delivery.pk)
        deliver_notification_email(delivery_id=delivery.pk)

        mocked_send.assert_called_once()

    def test_create_notifications_deduplicates_recipients(self):
        second_user = User.objects.create_user(
            email="notification-service-two@example.com",
            password="Notification-Test-Password-123!",
        )
        created = create_notifications(
            users=[self.user, second_user, self.user],
            notification_type=Notification.Type.SYSTEM_ALERT,
            title="System update",
            message="A system update is available.",
        )

        self.assertEqual(len(created), 2)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(
            set(Notification.objects.values_list("user_id", flat=True)),
            {self.user.pk, second_user.pk},
        )
