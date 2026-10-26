"""
API tests for account registration, email verification, and JWT policies.

These tests use Django's test database and never send real email.
Run with:
    python manage.py test apps.accounts.test_auth_api
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.authentication import EligibleAccountJWTAuthentication

from apps.accounts.services.email_verification import (
    generate_verification_token,
)

User = get_user_model()


class CustomerRegistrationAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:register")
        self.valid_payload = {
            "email": "new.customer@example.com",
            "password": "A-Strong-Unique-Test-Password-482!",
            "password_confirm": "A-Strong-Unique-Test-Password-482!",
        }

    @patch("apps.accounts.services.registration.send_verification_email")
    def test_valid_registration_creates_unverified_customer(self, mock_send_email):
        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], self.valid_payload["email"])
        self.assertEqual(response.data["user"]["role"], User.Role.CUSTOMER)
        self.assertFalse(response.data["user"]["email_verified"])

        user = User.objects.get(email=self.valid_payload["email"])
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.status, User.Status.ACTIVE)
        self.assertFalse(user.email_verified)
        self.assertTrue(user.check_password(self.valid_payload["password"]))
        mock_send_email.assert_called_once_with(user)

    @patch("apps.accounts.services.registration.send_verification_email")
    def test_public_registration_cannot_choose_privileged_role(self, mock_send_email):
        payload = {**self.valid_payload, "role": User.Role.ADMIN}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], User.Role.CUSTOMER)
        mock_send_email.assert_called_once()

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            email=self.valid_payload["email"],
            password=self.valid_payload["password"],
        )

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_confirmation_mismatch_is_rejected(self):
        payload = {
            **self.valid_payload,
            "password_confirm": "Different-Password-482!",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)

    def test_weak_password_is_rejected(self):
        payload = {
            **self.valid_payload,
            "password": "123",
            "password_confirm": "123",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:verify-email")
        self.user = User.objects.create_user(
            email="verify.me@example.com",
            password="A-Strong-Unique-Test-Password-482!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            email_verified=False,
        )

    def test_valid_token_verifies_email(self):
        token = generate_verification_token(self.user)

        response = self.client.post(self.url, {"token": token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["email_verified"])

        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNotNone(self.user.email_verified_at)

    def test_invalid_token_is_rejected(self):
        response = self.client.post(
            self.url,
            {"token": "not-a-valid-signed-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_expired_token_is_rejected(self):
        token = generate_verification_token(self.user)

        with patch(
            "apps.accounts.services.email_verification.signing.loads",
            side_effect=signing.SignatureExpired("expired"),
        ):
            response = self.client.post(
                self.url,
                {"token": token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data["detail"].lower())
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_already_verified_email_is_rejected_on_reuse(self):
        token = generate_verification_token(self.user)

        first_response = self.client.post(
            self.url, {"token": token}, format="json"
        )
        second_response = self.client.post(
            self.url, {"token": token}, format="json"
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_account_cannot_be_verified(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        token = generate_verification_token(self.user)

        response = self.client.post(self.url, {"token": token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_malformed_request_is_rejected(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JWTLoginAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:token-obtain-pair")
        self.password = "A-Strong-Unique-Test-Password-482!"
        self.user = User.objects.create_user(
            email="jwt.customer@example.com",
            password=self.password,
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            email_verified=True,
        )

    def login(self, email=None, password=None):
        return self.client.post(
            self.url,
            {
                "email": email or self.user.email,
                "password": self.password if password is None else password,
            },
            format="json",
        )

    def test_verified_active_user_receives_access_and_refresh_tokens(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("access"))
        self.assertTrue(response.data.get("refresh"))

    def test_unverified_user_cannot_log_in(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.login()

        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_suspended_user_cannot_log_in(self):
        self.user.status = User.Status.SUSPENDED
        self.user.save(update_fields=["status"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_status_user_cannot_log_in(self):
        self.user.status = User.Status.INACTIVE
        self.user.save(update_fields=["status"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_password_is_rejected(self):
        response = self.login(password="Definitely-Wrong-Password-923!")

        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_email_is_rejected(self):
        response = self.login(email="missing.user@example.com")

        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

class JWTRefreshAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:token-refresh")
        self.user = User.objects.create_user(
            email="refresh.customer@example.com",
            password="A-Strong-Unique-Test-Password-482!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            email_verified=True,
        )

    def make_refresh_token(self):
        return str(RefreshToken.for_user(self.user))

    def post_refresh(self, token):
        return self.client.post(
            self.url,
            {"refresh": token},
            format="json",
        )

    def test_valid_refresh_token_returns_new_access_token(self):
        response = self.post_refresh(self.make_refresh_token())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("access"))

    def test_invalid_refresh_token_is_rejected(self):
        response = self.post_refresh("not-a-valid-refresh-token")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_refresh_is_rejected_for_unverified_user(self):
        token = self.make_refresh_token()

        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])

        response = self.post_refresh(token)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_refresh_is_rejected_for_suspended_user(self):
        token = self.make_refresh_token()

        self.user.status = User.Status.SUSPENDED
        self.user.save(update_fields=["status"])

        response = self.post_refresh(token)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_refresh_is_rejected_for_inactive_user(self):
        token = self.make_refresh_token()

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.post_refresh(token)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_missing_refresh_token_is_rejected(self):
        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

class ExistingAccessTokenEligibilityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="access.token@example.com",
            password="A-Strong-Unique-Test-Password-482!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            email_verified=True,
        )

        self.access_token = str(RefreshToken.for_user(self.user).access_token)

        class ProtectedTestView(APIView):
            authentication_classes = [EligibleAccountJWTAuthentication]
            permission_classes = [IsAuthenticated]

            def get(self, request):
                return Response({"detail": "Access granted."})

        self.view = ProtectedTestView.as_view()
        self.factory = APIRequestFactory()

    def make_request(self):
        request = self.factory.get(
            "/test-protected/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        return self.view(request)

    def test_active_verified_user_can_use_access_token(self):
        response = self.make_request()
        self.assertEqual(response.status_code, 200)

    def test_suspended_user_cannot_use_existing_access_token(self):
        self.user.status = User.Status.SUSPENDED
        self.user.save(update_fields=["status"])

        response = self.make_request()
        self.assertEqual(response.status_code, 401)

    def test_inactive_status_user_cannot_use_existing_access_token(self):
        self.user.status = User.Status.INACTIVE
        self.user.save(update_fields=["status"])

        response = self.make_request()
        self.assertEqual(response.status_code, 401)

    def test_unverified_user_cannot_use_existing_access_token(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])

        response = self.make_request()
        self.assertEqual(response.status_code, 401)

    def test_deactivated_user_cannot_use_existing_access_token(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.make_request()
        self.assertEqual(response.status_code, 401)