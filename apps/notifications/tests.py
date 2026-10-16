import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification, NotificationDelivery

User = get_user_model()


class NotificationModelTests(TestCase):
    """Tests notification creation, relationships, and read state."""

    def setUp(self):
        # Create a customer to receive notifications.
        self.user = User.objects.create_user(
            email="notification-test@example.com",
            password="TestPassword!123",
        )

    def test_notification_creation(self):
        # Verify a notification is saved with the expected values.
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_CREATED,
            title="Ticket created",
            message="Your support ticket was created successfully.",
        )

        self.assertIsInstance(notification.id, uuid.UUID)
        self.assertEqual(notification.user, self.user)
        self.assertEqual(
            notification.notification_type,
            Notification.Type.TICKET_CREATED,
        )
        self.assertEqual(notification.title, "Ticket created")
        self.assertIsNone(notification.read_at)

    def test_notification_creation_timestamp(self):
        # Verify Django automatically records the creation timestamp.
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.SYSTEM_ALERT,
            title="System notice",
            message="A system notice was generated.",
        )

        self.assertIsNotNone(notification.created_at)

    def test_notification_string_representation(self):
        # Verify the model produces a readable description.
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_CREATED,
            title="Ticket created",
            message="Your ticket was created.",
        )

        self.assertEqual(
            str(notification),
            "TICKET_CREATED: Ticket created",
        )

    def test_notification_can_be_marked_as_read(self):
        # Verify the optional read timestamp can be populated.
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_UPDATED,
            title="Ticket updated",
            message="Your ticket was updated.",
        )

        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_user_can_have_multiple_notifications(self):
        # Verify the user reverse relationship returns their notifications.
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_CREATED,
            title="First notification",
            message="First message.",
        )
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_UPDATED,
            title="Second notification",
            message="Second message.",
        )

        self.assertEqual(self.user.notifications.count(), 2)

    def test_notifications_are_ordered_newest_first(self):
        # Verify the model's default ordering places newer records first.
        older = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_CREATED,
            title="Older notification",
            message="Older message.",
        )
        newer = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_UPDATED,
            title="Newer notification",
            message="Newer message.",
        )

        notifications = list(Notification.objects.all())

        self.assertEqual(notifications[0], newer)
        self.assertEqual(notifications[1], older)


class NotificationDeliveryModelTests(TestCase):
    """Tests delivery records and their relationship to notifications."""

    def setUp(self):
        # Create a recipient and a notification for delivery tests.
        self.user = User.objects.create_user(
            email="delivery-test@example.com",
            password="TestPassword!123",
        )

        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.Type.TICKET_CREATED,
            title="Ticket created",
            message="Your support ticket was created successfully.",
        )

    def test_delivery_creation(self):
        # Verify a delivery receives its configured defaults.
        delivery = NotificationDelivery.objects.create(
            notification=self.notification,
        )

        self.assertIsInstance(delivery.id, uuid.UUID)
        self.assertEqual(delivery.notification, self.notification)
        self.assertEqual(
            delivery.channel,
            NotificationDelivery.Channel.EMAIL,
        )
        self.assertEqual(
            delivery.provider,
            NotificationDelivery.Provider.RESEND,
        )
        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.PENDING,
        )
        self.assertEqual(delivery.attempt_count, 0)

    def test_delivery_creation_timestamps(self):
        # Verify creation and update timestamps are populated.
        delivery = NotificationDelivery.objects.create(
            notification=self.notification,
        )

        self.assertIsNotNone(delivery.created_at)
        self.assertIsNotNone(delivery.updated_at)

    def test_delivery_can_be_marked_sent(self):
        # Verify successful delivery details can be persisted.
        delivery = NotificationDelivery.objects.create(
            notification=self.notification,
        )

        delivery.status = NotificationDelivery.Status.SENT
        delivery.sent_at = timezone.now()
        delivery.attempt_count = 1
        delivery.save()

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.SENT,
        )
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.attempt_count, 1)

    def test_delivery_can_record_failure(self):
        # Verify failure details can be stored for troubleshooting.
        delivery = NotificationDelivery.objects.create(
            notification=self.notification,
        )

        delivery.status = NotificationDelivery.Status.FAILED
        delivery.failed_at = timezone.now()
        delivery.error_message = "Provider request failed."
        delivery.attempt_count = 1
        delivery.save()

        delivery.refresh_from_db()

        self.assertEqual(
            delivery.status,
            NotificationDelivery.Status.FAILED,
        )
        self.assertIsNotNone(delivery.failed_at)
        self.assertEqual(
            delivery.error_message,
            "Provider request failed.",
        )
        self.assertEqual(delivery.attempt_count, 1)

    def test_notification_can_have_multiple_deliveries(self):
        # Verify one notification can track multiple delivery records.
        NotificationDelivery.objects.create(
            notification=self.notification,
        )
        NotificationDelivery.objects.create(
            notification=self.notification,
        )

        self.assertEqual(self.notification.deliveries.count(), 2)

    def test_deleting_notification_deletes_deliveries(self):
        # Verify the configured CASCADE relationship removes child records.
        NotificationDelivery.objects.create(
            notification=self.notification,
        )

        self.notification.delete()

        self.assertEqual(NotificationDelivery.objects.count(), 0)