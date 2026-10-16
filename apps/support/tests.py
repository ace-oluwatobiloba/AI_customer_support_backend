from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import (
    Ticket,
    TicketAssignment,
    TicketEscalation,
)


User = get_user_model()


class TicketWorkflowModelTest(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        self.agent = User.objects.create_user(
            email="agent@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="AdminPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )

    def test_ticket_assignment_and_escalation_workflow(self):

        # 1. Create ticket
        ticket = Ticket.objects.create(
            ticket_number="TKT-20261008-0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Unable to access my account",
            description="I cannot log into my account.",
            priority=Ticket.Priority.HIGH,
            category=Ticket.Category.ACCOUNT,
        )

        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertEqual(ticket.customer, self.customer)
        self.assertEqual(ticket.created_by, self.customer)

        # 2. Assign ticket to agent
        assignment = TicketAssignment.objects.create(
            ticket=ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Account issue requires agent assistance.",
        )

        self.assertEqual(assignment.ticket, ticket)
        self.assertEqual(assignment.agent, self.agent)
        self.assertEqual(assignment.assigned_by, self.admin)

        # 3. Change ticket status to in progress
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save()

        ticket.refresh_from_db()

        self.assertEqual(
            ticket.status,
            Ticket.Status.IN_PROGRESS
        )

        # 4. Escalate ticket
        escalation = TicketEscalation.objects.create(
            ticket=ticket,
            escalated_by=self.agent,
            reason="Customer requires human intervention.",
            trigger=TicketEscalation.Trigger.AGENT_REQUEST,
        )

        # 5. Mark ticket as escalated
        ticket.status = Ticket.Status.ESCALATED
        ticket.save()

        ticket.refresh_from_db()

        # 6. Verify escalation
        self.assertEqual(
            escalation.ticket,
            ticket
        )

        self.assertEqual(
            escalation.escalated_by,
            self.agent
        )

        self.assertEqual(
            escalation.trigger,
            TicketEscalation.Trigger.AGENT_REQUEST
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.ESCALATED
        )

        # 7. Verify reverse relationships
        self.assertEqual(
            ticket.assignments.count(),
            1
        )

        self.assertEqual(
            ticket.escalations.count(),
            1
        )

        self.assertEqual(
            self.agent.ticket_assignments.count(),
            1
        )

        self.assertEqual(
            self.agent.ticket_escalations.count(),
            1
        )