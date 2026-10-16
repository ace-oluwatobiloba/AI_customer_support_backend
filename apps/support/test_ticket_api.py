"""
API regression tests for support ticket creation and access control.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.support.models import Ticket, TicketAssignment


User = get_user_model()


class TicketAPITestCase(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer1@example.com",
            password="Customer-Test-Password-123!",
            role=User.Role.CUSTOMER,
            status=User.Status.ACTIVE,
            is_active=True,
            email_verified=True,
        )

        self.other_customer = User.objects.create_user(
            email="customer2@example.com",
            password="Customer-Test-Password-456!",
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

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="Admin-Test-Password-123!",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_active=True,
            is_staff=True,
            email_verified=True,
        )

        self.customer_ticket = Ticket.objects.create(
            ticket_number="TKT-20261015-TEST0001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Customer one issue",
            description="A test issue belonging to customer one.",
            category=Ticket.Category.ACCOUNT,
        )

        self.other_customer_ticket = Ticket.objects.create(
            ticket_number="TKT-20261015-TEST0002",
            customer=self.other_customer,
            created_by=self.other_customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Customer two issue",
            description="A test issue belonging to customer two.",
            category=Ticket.Category.BILLING,
        )

        self.ticket_list_url = reverse(
            "support:ticket-list-create"
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}"
        )

    def test_customer_can_create_ticket(self):
        self.authenticate_as(self.customer)

        response = self.client.post(
            self.ticket_list_url,
            {
                "title": "Cannot access account",
                "description": "I need assistance accessing my account.",
                "category": Ticket.Category.ACCOUNT,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        ticket = Ticket.objects.get(
            title="Cannot access account"
        )

        self.assertEqual(ticket.customer, self.customer)
        self.assertEqual(ticket.created_by, self.customer)
        self.assertEqual(
            ticket.created_source,
            Ticket.CreatedSource.CUSTOMER,
        )
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertEqual(ticket.priority, Ticket.Priority.MEDIUM)

    def test_customer_can_list_only_own_tickets(self):
        self.authenticate_as(self.customer)

        response = self.client.get(self.ticket_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            str(item["id"])
            for item in response.data
        }

        self.assertIn(
            str(self.customer_ticket.id),
            returned_ids,
        )

        self.assertNotIn(
            str(self.other_customer_ticket.id),
            returned_ids,
        )

    def test_customer_cannot_retrieve_another_customers_ticket(self):
        self.authenticate_as(self.customer)

        url = reverse(
            "support:ticket-detail",
            kwargs={"ticket_id": self.other_customer_ticket.id},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_agent_sees_only_actively_assigned_tickets(self):
        assigned_ticket = self.customer_ticket

        TicketAssignment.objects.create(
            ticket=assigned_ticket,
            agent=self.agent,
            assigned_by=self.admin,
            reason="Test assignment",
        )

        self.authenticate_as(self.agent)

        response = self.client.get(self.ticket_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            str(item["id"])
            for item in response.data
        }

        self.assertIn(
            str(assigned_ticket.id),
            returned_ids,
        )

        self.assertNotIn(
            str(self.other_customer_ticket.id),
            returned_ids,
        )

    def test_admin_can_list_all_tickets(self):
        self.authenticate_as(self.admin)

        response = self.client.get(self.ticket_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            str(item["id"])
            for item in response.data
        }

        self.assertIn(
            str(self.customer_ticket.id),
            returned_ids,
        )

        self.assertIn(
            str(self.other_customer_ticket.id),
            returned_ids,
        )

    def test_unauthenticated_user_cannot_list_tickets(self):
        response = self.client.get(self.ticket_list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_customer_cannot_override_server_managed_fields(self):
        self.authenticate_as(self.customer)

        response = self.client.post(
            self.ticket_list_url,
            {
                "title": "Attempted privilege escalation",
                "description": "Testing protected fields.",
                "category": Ticket.Category.OTHER,
                "customer": str(self.other_customer.id),
                "created_by": str(self.other_customer.id),
                "created_source": Ticket.CreatedSource.ADMIN,
                "status": Ticket.Status.RESOLVED,
                "priority": Ticket.Priority.URGENT,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        ticket = Ticket.objects.get(
            title="Attempted privilege escalation"
        )

        self.assertEqual(ticket.customer, self.customer)
        self.assertEqual(ticket.created_by, self.customer)
        self.assertEqual(
            ticket.created_source,
            Ticket.CreatedSource.CUSTOMER,
        )
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertEqual(ticket.priority, Ticket.Priority.MEDIUM)