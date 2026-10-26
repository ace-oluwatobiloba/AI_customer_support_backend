from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class AdminSecurityTest(TestCase):
    """Test Django Admin authentication and authorization."""

    def setUp(self):
        self.password = "StrongAdminPass123!"

        self.admin_user = User.objects.create_superuser(
            email="admin-security@example.com",
            password=self.password,
        )

        self.admin_user.email_verified = True
        self.admin_user.save(update_fields=["email_verified"])

        self.admin_url = reverse("secure_admin:index")
        self.login_url = reverse("secure_admin:login")

    def login_data(self):
        return {
            "username": self.admin_user.email,
            "password": self.password,
        }

    def test_eligible_admin_can_log_in(self):
        response = self.client.post(
            f"{self.login_url}?next={self.admin_url}",
            self.login_data(),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], self.admin_url)
        self.assertIn("_auth_user_id", self.client.session)

    def test_unverified_admin_cannot_log_in(self):
        self.admin_user.email_verified = False
        self.admin_user.save(update_fields=["email_verified"])

        response = self.client.post(
            f"{self.login_url}?next={self.admin_url}",
            self.login_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_suspended_admin_cannot_access_admin(self):
        self.admin_user.status = User.Status.SUSPENDED
        self.admin_user.save(update_fields=["status"])

        self.client.force_login(self.admin_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_customer_role_cannot_access_admin(self):
        self.admin_user.role = User.Role.CUSTOMER
        self.admin_user.save(update_fields=["role"])

        self.client.force_login(self.admin_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_non_staff_user_cannot_access_admin(self):
        self.admin_user.is_staff = False
        self.admin_user.save(update_fields=["is_staff"])

        self.client.force_login(self.admin_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_existing_session_loses_access_when_admin_is_suspended(self):
        self.client.force_login(self.admin_user)

        initial_response = self.client.get(self.admin_url)
        self.assertEqual(initial_response.status_code, 200)

        self.admin_user.status = User.Status.SUSPENDED
        self.admin_user.save(update_fields=["status"])

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_inactive_admin_cannot_access_admin(self):
        self.admin_user.status = User.Status.INACTIVE
        self.admin_user.save(update_fields=["status"])

        self.client.force_login(self.admin_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_django_inactive_admin_cannot_access_admin(self):
        self.admin_user.is_active = False
        self.admin_user.save(update_fields=["is_active"])

        self.client.force_login(self.admin_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_customer_role_cannot_log_in_to_admin(self):
        self.admin_user.role = User.Role.CUSTOMER
        self.admin_user.save(update_fields=["role"])

        response = self.client.post(
            f"{self.login_url}?next={self.admin_url}",
            self.login_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)