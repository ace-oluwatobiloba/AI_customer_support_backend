from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import AgentProfile, EmployeeInvitation, User
from apps.accounts.services.employee_onboarding import (
    EmployeeOnboardingError,
    EmployeeInvitationDeliveryError,
    accept_employee_invitation,
    invite_employee,
)
from apps.accounts.services.email_delivery import EmailDeliveryError


class EmployeeInvitationServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="onboarding-admin@example.com",
            password="AdminPass123!",
        )

    def get_raw_token_from_email(self, send_mail_mock):
        """Extract the invitation token from the mocked email message."""
        send_mail_mock.assert_called_once()

        call = send_mail_mock.call_args

        # Support both positional and keyword arguments to send_mail().
        if "message" in call.kwargs:
            message = call.kwargs["message"]
        else:
            message = call.args[1]

        parts = message.split("\n\n")

        self.assertGreaterEqual(
            len(parts),
            3,
            "The invitation email does not contain the expected token section.",
        )

        return parts[2].strip()

    @override_settings(
        PUBLIC_API_BASE_URL="https://example.test",
        DEFAULT_FROM_EMAIL="noreply@example.test",
    )
    @patch(
        "apps.accounts.services.employee_onboarding.send_mail",
        return_value=1,
    )
    def test_invitation_acceptance_provisions_verified_agent(self, send_mail_mock):
        invitation = invite_employee(
            invited_by=self.admin,
            email="new.agent@example.com",
            employee_code="AGT-NEW-001",
            department="Customer Support",
            specialization="Reservations",
        )

        raw_token = self.get_raw_token_from_email(send_mail_mock)

        agent = accept_employee_invitation(
            token=raw_token,
            password="Strong-Agent-Password-928!",
            password_confirm="Strong-Agent-Password-928!",
        )

        agent.refresh_from_db()
        invitation.refresh_from_db()

        self.assertEqual(agent.role, User.Role.AGENT)
        self.assertTrue(agent.email_verified)
        self.assertTrue(agent.check_password("Strong-Agent-Password-928!"))
        self.assertEqual(
            agent.agent_profile.employee_code,
            "AGT-NEW-001",
        )
        self.assertEqual(
            invitation.status,
            EmployeeInvitation.Status.ACCEPTED,
        )
        self.assertIsNotNone(invitation.accepted_at)

    @patch(
        "apps.accounts.services.employee_onboarding.send_mail",
        return_value=1,
    )
    def test_non_admin_cannot_invite_employee(self, send_mail_mock):
        customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
        )

        with self.assertRaises(EmployeeOnboardingError):
            invite_employee(
                invited_by=customer,
                email="agent@example.com",
                employee_code="AGT-NEW-002",
            )

        self.assertFalse(EmployeeInvitation.objects.exists())
        send_mail_mock.assert_not_called()

    @override_settings(
        PUBLIC_API_BASE_URL="https://example.test",
        DEFAULT_FROM_EMAIL="noreply@example.test",
    )
    @patch(
        "apps.accounts.services.employee_onboarding.send_mail",
        return_value=1,
    )
    def test_invitation_is_single_use(self, send_mail_mock):
        invite_employee(
            invited_by=self.admin,
            email="single.agent@example.com",
            employee_code="AGT-NEW-003",
        )

        raw_token = self.get_raw_token_from_email(send_mail_mock)

        kwargs = {
            "token": raw_token,
            "password": "Strong-Agent-Password-928!",
            "password_confirm": "Strong-Agent-Password-928!",
        }

        accept_employee_invitation(**kwargs)

        with self.assertRaises(EmployeeOnboardingError):
            accept_employee_invitation(**kwargs)


    @patch(
        "apps.accounts.services.employee_onboarding.send_mail",
        side_effect=EmailDeliveryError("provider unavailable"),
    )
    def test_failed_delivery_revokes_invitation_and_raises_service_error(self, send_mail_mock):
        with self.assertRaises(EmployeeInvitationDeliveryError):
            invite_employee(
                invited_by=self.admin,
                email="delivery-failed@example.com",
                employee_code="AGT-DELIVERY-FAIL",
            )

        invitation = EmployeeInvitation.objects.get(
            email="delivery-failed@example.com"
        )
        self.assertEqual(invitation.status, EmployeeInvitation.Status.REVOKED)
        send_mail_mock.assert_called_once()



class EmployeeManagementAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="api-admin@example.com",
            password="AdminPass123!",
        )

        self.customer = User.objects.create_user(
            email="api-customer@example.com",
            password="CustomerPass123!",
        )

    def test_customer_cannot_invite_employees(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            reverse("accounts:employee-invitations"),
            {
                "email": "agent@example.com",
                "employee_code": "AGT-API-001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_agents(self):
        agent = User.objects.create_user(
            email="agent-list@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
            email_verified=True,
        )

        AgentProfile.objects.create(
            user=agent,
            employee_code="AGT-LIST-001",
        )

        self.client.force_authenticate(self.admin)

        response = self.client.get(
            reverse("accounts:agent-list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
