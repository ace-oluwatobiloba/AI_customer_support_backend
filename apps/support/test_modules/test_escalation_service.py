"""
Tests for ticket escalation business logic.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.conversations.models import Conversation
from apps.support.models import Ticket, TicketEscalation
from apps.support.services import (
    TicketEscalationError,
    escalate_ticket,
)


User = get_user_model()


class TicketEscalationServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer-escalation@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.agent = User.objects.create_user(
            email="agent-escalation@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.admin = User.objects.create_user(
            email="admin-escalation@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
            email_verified=True,
        )

        self.ticket = Ticket.objects.create(
            ticket_number="TKT-20261016-ESCL0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Payment issue",
            description="The customer reports a failed payment.",
            category=Ticket.Category.BILLING,
        )

        self.conversation = Conversation.objects.create(
            customer=self.customer,
            ticket=self.ticket,
            title="Payment support conversation",
        )

    def test_agent_can_escalate_ticket(self):
        escalation = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=self.agent,
            reason="The issue requires specialist investigation.",
            trigger=TicketEscalation.Trigger.AGENT_REQUEST,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(escalation.ticket, self.ticket)
        self.assertEqual(escalation.escalated_by, self.agent)
        self.assertEqual(
            escalation.trigger,
            TicketEscalation.Trigger.AGENT_REQUEST,
        )
        self.assertEqual(self.ticket.status, Ticket.Status.ESCALATED)

    def test_admin_can_escalate_ticket(self):
        escalation = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=self.admin,
            reason="Administrative escalation.",
            trigger=TicketEscalation.Trigger.ADMIN_REQUEST,
        )

        self.assertEqual(escalation.escalated_by, self.admin)

    def test_customer_cannot_escalate_through_manual_service(self):
        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=self.ticket.id,
                escalated_by=self.customer,
                reason="Please escalate my issue.",
                trigger=TicketEscalation.Trigger.CUSTOMER_REQUEST,
            )

        self.assertFalse(
            TicketEscalation.objects.filter(
                ticket=self.ticket
            ).exists()
        )

    def test_escalation_reason_is_required(self):
        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=self.ticket.id,
                escalated_by=self.agent,
                reason="   ",
                trigger=TicketEscalation.Trigger.AGENT_REQUEST,
            )

        self.assertFalse(
            TicketEscalation.objects.filter(
                ticket=self.ticket
            ).exists()
        )

    def test_invalid_trigger_is_rejected(self):
        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=self.ticket.id,
                escalated_by=self.agent,
                reason="Invalid trigger test.",
                trigger="INVALID_TRIGGER",
            )

    def test_resolved_ticket_cannot_be_escalated(self):
        self.ticket.status = Ticket.Status.RESOLVED
        self.ticket.save(update_fields=["status"])

        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=self.ticket.id,
                escalated_by=self.agent,
                reason="Attempt to escalate resolved ticket.",
                trigger=TicketEscalation.Trigger.AGENT_REQUEST,
            )

    def test_closed_ticket_cannot_be_escalated(self):
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.save(update_fields=["status"])

        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=self.ticket.id,
                escalated_by=self.agent,
                reason="Attempt to escalate closed ticket.",
                trigger=TicketEscalation.Trigger.AGENT_REQUEST,
            )

    def test_conversation_can_be_linked_to_escalation(self):
        escalation = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=self.agent,
            reason="AI could not resolve the payment issue.",
            trigger=TicketEscalation.Trigger.AI_CONFIDENCE,
            conversation=self.conversation,
        )

        self.assertEqual(
            escalation.conversation,
            self.conversation,
        )

    def test_conversation_from_another_ticket_is_rejected(self):
        another_ticket = Ticket.objects.create(
            ticket_number="TKT-20261016-ESCL0002",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Different issue",
            description="A separate support issue.",
            category=Ticket.Category.OTHER,
        )

        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=another_ticket.id,
                escalated_by=self.agent,
                reason="Testing conversation ownership.",
                trigger=TicketEscalation.Trigger.AGENT_REQUEST,
                conversation=self.conversation,
            )

    def test_automated_escalation_can_have_no_initiating_user(self):
        escalation = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=None,
            reason="Automated escalation based on AI confidence.",
            trigger=TicketEscalation.Trigger.AI_CONFIDENCE,
        )

        self.assertIsNone(escalation.escalated_by)
        self.assertEqual(
            escalation.trigger,
            TicketEscalation.Trigger.AI_CONFIDENCE,
        )

    def test_repeated_escalation_preserves_history(self):
        first = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=self.agent,
            reason="First escalation.",
            trigger=TicketEscalation.Trigger.AGENT_REQUEST,
        )

        second = escalate_ticket(
            ticket_id=self.ticket.id,
            escalated_by=self.admin,
            reason="Further escalation.",
            trigger=TicketEscalation.Trigger.ADMIN_REQUEST,
        )

        self.assertNotEqual(first.id, second.id)

        self.assertEqual(
            TicketEscalation.objects.filter(
                ticket=self.ticket
            ).count(),
            2,
        )

        self.assertTrue(
            TicketEscalation.objects.filter(
                id=first.id,
                reason="First escalation.",
            ).exists()
        )

    def test_nonexistent_ticket_is_rejected(self):
        import uuid

        with self.assertRaises(TicketEscalationError):
            escalate_ticket(
                ticket_id=uuid.uuid4(),
                escalated_by=self.agent,
                reason="Ticket does not exist.",
                trigger=TicketEscalation.Trigger.AGENT_REQUEST,
            )