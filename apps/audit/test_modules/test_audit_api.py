"""API and admin tests for read-only administrator audit access."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.admin import secure_admin_site
from apps.audit.admin import AuditLogAdmin
from apps.audit.models import AuditLog

User = get_user_model()


class AuditLogAPITests(APITestCase):
    def setUp(self):
        self.admin = self.make_user(
            "admin", User.Role.ADMIN, is_staff=True, is_superuser=True
        )
        self.customer = self.make_user("customer", User.Role.CUSTOMER)
        self.agent = self.make_user("agent", User.Role.AGENT)

        self.admin_event = self.make_event(
            self.admin, "TICKET_CREATED", "Ticket"
        )
        self.customer_event = self.make_event(
            self.customer, "USER_REGISTERED", "User"
        )
        self.list_url = reverse("audit:audit-log-list")

    def make_user(self, prefix, role, **extra):
        return User.objects.create_user(
            email=f"{prefix}.audit-api@example.com",
            password="Audit-API-Test-Password-123!",
            role=role,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
            **extra,
        )

    def make_event(self, actor, action, entity_type):
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            metadata={"test": True},
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def test_unauthenticated_user_cannot_list_audit_logs(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_audit_logs(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(
            returned_ids,
            {str(self.admin_event.pk), str(self.customer_event.pk)},
        )

    def test_customer_cannot_list_audit_logs(self):
        self.authenticate_as(self.customer)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_agent_cannot_list_audit_logs(self):
        self.authenticate_as(self.agent)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_retrieve_audit_log(self):
        self.authenticate_as(self.admin)
        url = reverse(
            "audit:audit-log-detail",
            kwargs={"audit_log_id": self.customer_event.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], "USER_REGISTERED")
        self.assertEqual(
            response.data["actor_email"],
            self.customer.email,
        )
        self.assertEqual(response.data["metadata"], {"test": True})

    def test_customer_cannot_retrieve_audit_log(self):
        self.authenticate_as(self.customer)
        url = reverse(
            "audit:audit-log-detail",
            kwargs={"audit_log_id": self.admin_event.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_can_filter_by_action(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.list_url, {"action": "TICKET_CREATED"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["action"], "TICKET_CREATED")

    def test_list_can_filter_by_entity_type(self):
        self.authenticate_as(self.admin)
        response = self.client.get(self.list_url, {"entity_type": "User"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["entity_type"], "User")

    def test_inactive_admin_is_rejected(self):
        self.admin.status = User.Status.SUSPENDED
        self.admin.save(update_fields=["status"])
        self.authenticate_as(self.admin)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_does_not_allow_mutation(self):
        self.authenticate_as(self.admin)
        response = self.client.post(self.list_url, {"action": "FORGED_EVENT"})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AuditLogAdminReadOnlyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email="audit-admin-site@example.com",
            password="Audit-Admin-Test-Password-123!",
        )
        self.model_admin = AuditLogAdmin(AuditLog, secure_admin_site)
        self.request = self.factory.get("/admin/audit/auditlog/")
        self.request.user = self.admin_user

    def test_audit_log_is_registered_on_secure_admin_site(self):
        self.assertIn(AuditLog, secure_admin_site._registry)

    def test_admin_cannot_add_audit_records(self):
        self.assertFalse(self.model_admin.has_add_permission(self.request))

    def test_admin_cannot_change_audit_records(self):
        self.assertFalse(self.model_admin.has_change_permission(self.request))

    def test_admin_cannot_delete_audit_records(self):
        self.assertFalse(self.model_admin.has_delete_permission(self.request))

    def test_admin_can_view_audit_records(self):
        self.assertTrue(self.model_admin.has_view_permission(self.request))
