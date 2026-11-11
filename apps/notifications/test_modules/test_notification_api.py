"""API tests for notification retrieval and read-state management."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification

User = get_user_model()


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.customer = self.make_user("customer", User.Role.CUSTOMER)
        self.other_customer = self.make_user("other", User.Role.CUSTOMER)
        self.agent = self.make_user("agent", User.Role.AGENT)
        self.admin = self.make_user("admin", User.Role.ADMIN)

        self.own_unread = self.make_notification(
            self.customer, "Own unread"
        )
        self.own_read = self.make_notification(
            self.customer, "Own read", read=True
        )
        self.other_notification = self.make_notification(
            self.other_customer, "Other user's notification"
        )

        self.list_url = reverse("notifications:notification-list")
        self.count_url = reverse("notifications:unread-count")
        self.mark_all_url = reverse("notifications:mark-all-read")

    def make_user(self, prefix, role):
        return User.objects.create_user(
            email=f"{prefix}.notification-api@example.com",
            password="Notification-API-Test-Password-123!",
            role=role,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

    def make_notification(self, user, title, read=False):
        return Notification.objects.create(
            user=user,
            notification_type=Notification.Type.SYSTEM_ALERT,
            title=title,
            message=f"Message for {title}.",
            read_at=timezone.now() if read else None,
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def test_unauthenticated_user_cannot_list_notifications(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_sees_only_own_notifications(self):
        self.authenticate_as(self.customer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(
            returned_ids,
            {str(self.own_unread.pk), str(self.own_read.pk)},
        )
        self.assertNotIn(str(self.other_notification.pk), returned_ids)

    def test_agent_can_list_own_notifications(self):
        notification = self.make_notification(self.agent, "Agent notice")
        self.authenticate_as(self.agent)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(notification.pk)],
        )

    def test_admin_can_list_only_own_notifications(self):
        admin_notice = self.make_notification(self.admin, "Admin notice")
        self.authenticate_as(self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(admin_notice.pk)],
        )

    def test_list_supports_bounded_page_size(self):
        self.authenticate_as(self.customer)
        response = self.client.get(self.list_url, {"page_size": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])

    def test_user_can_retrieve_own_notification(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "notifications:notification-detail",
            kwargs={"notification_id": self.own_unread.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.own_unread.pk))
        self.assertEqual(response.data["title"], "Own unread")

    def test_user_cannot_retrieve_another_users_notification(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "notifications:notification-detail",
            kwargs={"notification_id": self.other_notification.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unread_count_is_scoped_to_current_user(self):
        self.authenticate_as(self.customer)
        response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"unread_count": 1})

    def test_user_can_mark_own_notification_as_read(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "notifications:mark-read",
            kwargs={"notification_id": self.own_unread.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_unread.refresh_from_db()
        self.assertIsNotNone(self.own_unread.read_at)

    def test_mark_read_is_idempotent(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "notifications:mark-read",
            kwargs={"notification_id": self.own_read.pk},
        )
        original_read_at = self.own_read.read_at

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own_read.refresh_from_db()
        self.assertEqual(self.own_read.read_at, original_read_at)

    def test_user_cannot_mark_another_users_notification_as_read(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "notifications:mark-read",
            kwargs={"notification_id": self.other_notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_notification.refresh_from_db()
        self.assertIsNone(self.other_notification.read_at)

    def test_mark_all_read_changes_only_current_users_unread_notifications(self):
        second_unread = self.make_notification(
            self.customer, "Second unread"
        )
        self.authenticate_as(self.customer)

        response = self.client.post(self.mark_all_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)

        self.own_unread.refresh_from_db()
        second_unread.refresh_from_db()
        self.other_notification.refresh_from_db()
        self.assertIsNotNone(self.own_unread.read_at)
        self.assertIsNotNone(second_unread.read_at)
        self.assertIsNone(self.other_notification.read_at)

    def test_mark_all_read_is_safe_when_nothing_is_unread(self):
        self.authenticate_as(self.customer)
        self.client.post(self.mark_all_url)

        response = self.client.post(self.mark_all_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 0)

    def test_inactive_account_is_rejected(self):
        self.customer.status = User.Status.SUSPENDED
        self.customer.save(update_fields=["status"])
        self.authenticate_as(self.customer)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_notification_serializer_does_not_expose_delivery_records(self):
        self.authenticate_as(self.customer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertNotIn("deliveries", item)
        self.assertNotIn("user", item)
