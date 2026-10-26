"""
API tests for ticket assignment endpoints.

Covers authorization, assignment validation, assignment history,
and reassignment behaviour.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.support.models import Ticket, TicketAssignment


User = get_user_model()


class TicketAssignmentAPITestCase(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.agent = User.objects.create_user(
            email="agent@example.com",
            password="Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.second_agent = User.objects.create_user(
            email="agent2@example.com",
            password="Agent2-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.inactive_agent = User.objects.create_user(
            email="inactive-agent@example.com",
            password="Inactive-Agent-Test-Password-123!",
            role=User.Role.AGENT,
            status=User.Status.INACTIVE,
            is_active=False,
            email_verified=True,
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
            email_verified=True,
        )

        self.ticket = Ticket.objects.create(
            ticket_number="TKT-20261016-ASGN0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Unable to access account",
            description="The customer cannot access their account.",
            category=Ticket.Category.ACCOUNT,
        )

        self.assignment_url = reverse(
            "support:ticket-assignment-list-create",
            kwargs={"ticket_id": self.ticket.id},
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def test_admin_can_assign_active_agent(self):
        self.authenticate_as(self.admin)

        response = self.client.post(
            self.assignment_url,
            {
                "agent_id": str(self.agent.id),
                "reason": "Agent has relevant expertise.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        assignment = TicketAssignment.objects.get(
            ticket=self.ticket,
            agent=self.agent,
            unassigned_at__isnull=True,
        )

        self.assertEqual(assignment.assigned_by, self.admin)
        self.assertEqual(
            assignment.reason,
            "Agent has relevant expertise.",
        )

    def test_customer_cannot_assign_agent(self):
        self.authenticate_as(self.customer)

        response = self.client.post(
            self.assignment_url,
            {"agent_id": str(self.agent.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.data,
        )

        self.assertFalse(
            TicketAssignment.objects.filter(
                ticket=self.ticket
            ).exists()
        )

    def test_unauthenticated_user_cannot_assign_agent(self):
        response = self.client.post(
            self.assignment_url,
            {"agent_id": str(self.agent.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            response.data,
        )

    def test_admin_cannot_assign_inactive_agent(self):
        self.authenticate_as(self.admin)

        response = self.client.post(
            self.assignment_url,
            {"agent_id": str(self.inactive_agent.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

        self.assertFalse(
            TicketAssignment.objects.filter(
                ticket=self.ticket
            ).exists()
        )

    def test_admin_can_retrieve_assignment_history(self):
        previous_assignment = TicketAssignment.objects.create(
            ticket=self.ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Initial assignment.",
        )

        self.authenticate_as(self.admin)

        response = self.client.get(self.assignment_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(previous_assignment.id),
        )
        self.assertEqual(
            str(response.data[0]["agent"]),
            str(self.agent.id),
        )

    def test_customer_cannot_retrieve_assignment_history(self):
        self.authenticate_as(self.customer)

        response = self.client.get(self.assignment_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            response.data,
        )

    def test_reassignment_preserves_previous_assignment(self):
        previous_assignment = TicketAssignment.objects.create(
            ticket=self.ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Initial assignment.",
        )

        self.authenticate_as(self.admin)

        response = self.client.post(
            self.assignment_url,
            {
                "agent_id": str(self.second_agent.id),
                "reason": "Reassigned to another specialist.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        previous_assignment.refresh_from_db()

        self.assertIsNotNone(previous_assignment.unassigned_at)
        self.assertEqual(
            previous_assignment.agent,
            self.agent,
        )

        active_assignments = TicketAssignment.objects.filter(
            ticket=self.ticket,
            unassigned_at__isnull=True,
        )

        self.assertEqual(active_assignments.count(), 1)

        current_assignment = active_assignments.get()

        self.assertEqual(
            current_assignment.agent,
            self.second_agent,
        )
        self.assertEqual(
            current_assignment.assigned_by,
            self.admin,
        )

    def test_admin_cannot_assign_same_agent_twice(self):
        TicketAssignment.objects.create(
            ticket=self.ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Initial assignment.",
        )

        self.authenticate_as(self.admin)

        response = self.client.post(
            self.assignment_url,
            {"agent_id": str(self.agent.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

        self.assertEqual(
            TicketAssignment.objects.filter(
                ticket=self.ticket,
                unassigned_at__isnull=True,
            ).count(),
            1,
        )

    def test_assignment_for_nonexistent_ticket_returns_404(self):
        self.authenticate_as(self.admin)

        missing_ticket_url = reverse(
            "support:ticket-assignment-list-create",
            kwargs={
                "ticket_id": "00000000-0000-0000-0000-000000000001"
            },
        )

        response = self.client.post(
            missing_ticket_url,
            {"agent_id": str(self.agent.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            response.data,
        )