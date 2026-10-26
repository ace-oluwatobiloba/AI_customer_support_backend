from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.support.models import Ticket, TicketAssignment
from apps.support.services import (
    TicketAssignmentError,
    assign_ticket,
)

User = get_user_model()


class TicketAssignmentServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="assignment.customer@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
        )

        self.admin = User.objects.create_user(
            email="assignment.admin@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
        )

        self.agent = User.objects.create_user(
            email="assignment.agent@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
        )

        self.second_agent = User.objects.create_user(
            email="assignment.agent2@example.com",
            password="Agent-Test-Password-456!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
        )

        self.ticket = Ticket.objects.create(
            ticket_number="TKT-20261016-ASG00001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Assignment test",
            description="Testing ticket assignment.",
            category=Ticket.Category.OTHER,
        )

    def test_admin_can_assign_ticket_to_active_agent(self):
        assignment = assign_ticket(
            ticket_id=self.ticket.id,
            agent_id=self.agent.id,
            assigned_by=self.admin,
            reason="Initial assignment",
        )

        self.assertEqual(assignment.ticket, self.ticket)
        self.assertEqual(assignment.agent, self.agent)
        self.assertEqual(assignment.assigned_by, self.admin)
        self.assertIsNone(assignment.unassigned_at)

    def test_customer_cannot_assign_ticket(self):
        with self.assertRaises(TicketAssignmentError):
            assign_ticket(
                ticket_id=self.ticket.id,
                agent_id=self.agent.id,
                assigned_by=self.customer,
            )

        self.assertEqual(
            TicketAssignment.objects.filter(
                ticket=self.ticket
            ).count(),
            0,
        )

    def test_inactive_agent_cannot_receive_assignment(self):
        self.agent.is_active = False
        self.agent.save(update_fields=["is_active"])

        with self.assertRaises(TicketAssignmentError):
            assign_ticket(
                ticket_id=self.ticket.id,
                agent_id=self.agent.id,
                assigned_by=self.admin,
            )

    def test_customer_role_cannot_be_assigned_as_agent(self):
        with self.assertRaises(TicketAssignmentError):
            assign_ticket(
                ticket_id=self.ticket.id,
                agent_id=self.customer.id,
                assigned_by=self.admin,
            )

    def test_reassignment_preserves_previous_assignment(self):
        first_assignment = assign_ticket(
            ticket_id=self.ticket.id,
            agent_id=self.agent.id,
            assigned_by=self.admin,
            reason="Initial assignment",
        )

        second_assignment = assign_ticket(
            ticket_id=self.ticket.id,
            agent_id=self.second_agent.id,
            assigned_by=self.admin,
            reason="Reassignment",
        )

        first_assignment.refresh_from_db()

        self.assertIsNotNone(first_assignment.unassigned_at)
        self.assertEqual(second_assignment.agent, self.second_agent)

        self.assertEqual(
            TicketAssignment.objects.filter(
                ticket=self.ticket
            ).count(),
            2,
        )

        self.assertEqual(
            TicketAssignment.objects.filter(
                ticket=self.ticket,
                unassigned_at__isnull=True,
            ).count(),
            1,
        )

    def test_assigning_same_agent_twice_is_rejected(self):
        assign_ticket(
            ticket_id=self.ticket.id,
            agent_id=self.agent.id,
            assigned_by=self.admin,
        )

        with self.assertRaises(TicketAssignmentError):
            assign_ticket(
                ticket_id=self.ticket.id,
                agent_id=self.agent.id,
                assigned_by=self.admin,
            )

    def test_nonexistent_ticket_is_rejected(self):
        import uuid

        with self.assertRaises(TicketAssignmentError):
            assign_ticket(
                ticket_id=uuid.uuid4(),
                agent_id=self.agent.id,
                assigned_by=self.admin,
            )