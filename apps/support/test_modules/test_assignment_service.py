from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.support.models import Ticket, TicketAssignment
from apps.support.services import (
    TicketAssignmentError,
    assign_ticket,
    auto_assign_ticket,
)
from apps.notifications.models import Notification
from django.test import override_settings

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

    def test_auto_assigns_ticket_to_eligible_agent(self):
        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.ticket, self.ticket)
        self.assertEqual(assignment.agent.role, User.Role.AGENT)
        self.assertIsNone(assignment.assigned_by)
        self.assertIsNone(assignment.unassigned_at)
        self.assertIn("Automated assignment", assignment.reason)

        notification = Notification.objects.get(
            user=assignment.agent,
            notification_type=Notification.Type.TICKET_ASSIGNED,
        )

    def test_auto_assigns_to_least_loaded_agent(self):
        # Give the first agent one active ticket.
        existing_ticket = Ticket.objects.create(
            ticket_number="TKT-20261027-LOAD0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Existing workload",
            description="An existing assigned ticket.",
            category=Ticket.Category.OTHER,
            status=Ticket.Status.IN_PROGRESS,
        )

        TicketAssignment.objects.create(
            ticket=existing_ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Existing assignment",
        )

        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertEqual(assignment.agent, self.second_agent)

    @override_settings(SUPPORT_AGENT_MAX_ACTIVE_TICKETS=1)
    def test_auto_assignment_excludes_agents_at_capacity(self):
        existing_ticket = Ticket.objects.create(
            ticket_number="TKT-20261027-CAP00001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Agent at capacity",
            description="This agent already has an active ticket.",
            category=Ticket.Category.OTHER,
            status=Ticket.Status.IN_PROGRESS,
        )

        TicketAssignment.objects.create(
            ticket=existing_ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Existing assignment",
        )

        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertEqual(assignment.agent, self.second_agent)


    @override_settings(SUPPORT_AGENT_MAX_ACTIVE_TICKETS=1)
    def test_returns_none_when_all_agents_are_at_capacity(self):
        for index, agent in enumerate(
            [self.agent, self.second_agent],
            start=1,
        ):
            existing_ticket = Ticket.objects.create(
                ticket_number=f"TKT-20261027-FULL{index:04d}",
                customer=self.customer,
                created_by=self.customer,
                created_source=Ticket.CreatedSource.CUSTOMER,
                title=f"Existing ticket {index}",
                description="Ticket occupying agent capacity.",
                category=Ticket.Category.OTHER,
                status=Ticket.Status.IN_PROGRESS,
            )

            TicketAssignment.objects.create(
                ticket=existing_ticket,
                agent=agent,
                assigned_by=self.admin,
                reason="Existing assignment",
            )

        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertIsNone(assignment)
        self.assertFalse(
            TicketAssignment.objects.filter(
                ticket=self.ticket,
                unassigned_at__isnull=True,
            ).exists()
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.ESCALATED)

    def test_auto_assignment_does_not_replace_existing_assignment(self):
        existing_assignment = TicketAssignment.objects.create(
            ticket=self.ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Existing manual assignment",
        )

        result = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertEqual(result.id, existing_assignment.id)
        self.assertEqual(
            TicketAssignment.objects.filter(
                ticket=self.ticket,
                unassigned_at__isnull=True,
            ).count(),
            1,
        )
        self.assertFalse(
            Notification.objects.filter(
                user=self.second_agent,
                notification_type=Notification.Type.TICKET_ASSIGNED,
            ).exists()
        )


    def test_auto_assignment_excludes_inactive_agents(self):
        self.agent.is_active = False
        self.agent.save(update_fields=["is_active"])

        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertEqual(assignment.agent, self.second_agent)

    def test_auto_assignment_excludes_suspended_agents(self):
        self.agent.status = User.Status.SUSPENDED
        self.agent.save(update_fields=["status"])

        self.ticket.status = Ticket.Status.ESCALATED
        self.ticket.save(update_fields=["status"])

        assignment = auto_assign_ticket(ticket_id=self.ticket.id)

        self.assertEqual(assignment.agent, self.second_agent)
