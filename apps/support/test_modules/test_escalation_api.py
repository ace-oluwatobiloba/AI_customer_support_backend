"""
API tests for ticket escalation endpoints.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.conversations.models import Conversation
from apps.support.models import (
    Ticket,
    TicketAssignment,
    TicketEscalation,
)


User = get_user_model()


class TicketEscalationAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="escalation-customer@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.agent = User.objects.create_user(
            email="escalation-agent@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.other_agent = User.objects.create_user(
            email="escalation-agent2@example.com",
            password="Agent2-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.admin = User.objects.create_user(
            email="escalation-admin@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
            email_verified=True,
        )

        self.ticket = Ticket.objects.create(
            ticket_number="TKT-20261016-EAPI0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Payment failure",
            description="Payment did not complete.",
            category=Ticket.Category.BILLING,
        )

        self.conversation = Conversation.objects.create(
            customer=self.customer,
            ticket=self.ticket,
            title="Payment conversation",
        )

        self.url = reverse(
            "support:ticket-escalation-list-create",
            kwargs={"ticket_id": self.ticket.id},
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def assign_ticket_to_agent(self, agent=None):
        """Create an active assignment for the selected agent."""
        return TicketAssignment.objects.create(
            ticket=self.ticket,
            agent=agent or self.agent,
            assigned_by=self.admin,
            reason="Assigned for escalation API testing.",
        )

    def test_agent_can_create_escalation(self):
        self.assign_ticket_to_agent()
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "reason": "Requires specialist investigation.",
                "trigger": TicketEscalation.Trigger.AGENT_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.ESCALATED,
        )

        self.assertTrue(
            TicketEscalation.objects.filter(
                ticket=self.ticket,
                escalated_by=self.agent,
            ).exists()
        )

    def test_admin_can_create_escalation(self):
        self.authenticate_as(self.admin)

        response = self.client.post(
            self.url,
            {
                "reason": "Administrative review required.",
                "trigger": TicketEscalation.Trigger.ADMIN_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

    def test_customer_cannot_create_escalation(self):
        self.authenticate_as(self.customer)

        response = self.client.post(
            self.url,
            {
                "reason": "Please escalate my issue.",
                "trigger": TicketEscalation.Trigger.CUSTOMER_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.data,
        )

    def test_unauthenticated_user_cannot_create_escalation(self):
        response = self.client.post(
            self.url,
            {
                "reason": "Escalation test.",
                "trigger": TicketEscalation.Trigger.AGENT_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            response.data,
        )

    def test_escalation_reason_is_required(self):
        self.assign_ticket_to_agent()
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "trigger": TicketEscalation.Trigger.AGENT_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

    def test_invalid_trigger_is_rejected(self):
        self.assign_ticket_to_agent()
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "reason": "Invalid trigger test.",
                "trigger": "INVALID_TRIGGER",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

    def test_agent_can_retrieve_escalation_history(self):
        self.assign_ticket_to_agent()

        escalation = TicketEscalation.objects.create(
            ticket=self.ticket,
            escalated_by=self.agent,
            reason="Previous escalation.",
            trigger=TicketEscalation.Trigger.AGENT_REQUEST,
        )

        self.authenticate_as(self.agent)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            str(response.data[0]["id"]),
            str(escalation.id),
        )

    def test_admin_can_retrieve_escalation_history(self):
        escalation = TicketEscalation.objects.create(
            ticket=self.ticket,
            escalated_by=self.admin,
            reason="Administrative escalation.",
            trigger=TicketEscalation.Trigger.ADMIN_REQUEST,
        )

        self.authenticate_as(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            str(response.data[0]["id"]),
            str(escalation.id),
        )

    def test_customer_cannot_retrieve_escalation_history(self):
        self.authenticate_as(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.data,
        )

    def test_escalation_can_link_conversation(self):
        self.assign_ticket_to_agent()
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "reason": "AI could not resolve the issue.",
                "trigger": TicketEscalation.Trigger.AI_CONFIDENCE,
                "conversation_id": str(self.conversation.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        escalation = TicketEscalation.objects.get(
            ticket=self.ticket,
        )

        self.assertEqual(
            escalation.conversation,
            self.conversation,
        )

    def test_nonexistent_ticket_returns_404(self):
        self.authenticate_as(self.admin)

        missing_url = reverse(
            "support:ticket-escalation-list-create",
            kwargs={
                "ticket_id": "00000000-0000-0000-0000-000000000001",
            },
        )

        response = self.client.post(
            missing_url,
            {
                "reason": "Testing missing ticket.",
                "trigger": TicketEscalation.Trigger.ADMIN_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            response.data,
        )

    def test_agent_cannot_escalate_ticket_assigned_to_another_agent(self):
        self.assign_ticket_to_agent(self.other_agent)
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "reason": "Attempted unauthorized escalation.",
                "trigger": TicketEscalation.Trigger.AGENT_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            response.data,
        )

        self.assertFalse(
            TicketEscalation.objects.filter(
                ticket=self.ticket,
            ).exists()
        )

    def test_agent_can_escalate_ticket_assigned_to_them(self):
        self.assign_ticket_to_agent()
        self.authenticate_as(self.agent)

        response = self.client.post(
            self.url,
            {
                "reason": "The issue requires specialist support.",
                "trigger": TicketEscalation.Trigger.AGENT_REQUEST,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )