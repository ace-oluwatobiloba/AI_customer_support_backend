from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.conversations.models import Conversation, Message
from apps.support.models import Ticket, TicketAssignment


class ConversationHandoverAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.customer = User.objects.create_user(
            email="handover-customer@example.com",
            password="CustomerPass123!",
        )
        cls.assigned_agent = User.objects.create_user(
            email="assigned-agent@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
        )
        cls.other_agent = User.objects.create_user(
            email="other-agent@example.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
            status=User.Status.ACTIVE,
            is_active=True,
        )
        cls.admin = User.objects.create_superuser(
            email="handover-admin@example.com",
            password="AdminPass123!",
        )
        cls.ticket = Ticket.objects.create(
            ticket_number="TKT-HANDOVER-001",
            customer=cls.customer,
            created_by=cls.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Cannot access account",
            description="Customer needs help accessing the account.",
            status=Ticket.Status.ESCALATED,
        )
        cls.conversation = Conversation.objects.create(
            customer=cls.customer,
            ticket=cls.ticket,
            title="Account access support",
            status=Conversation.Status.ESCALATED,
        )
        TicketAssignment.objects.create(
            ticket=cls.ticket,
            agent=cls.assigned_agent,
            assigned_by=cls.admin,
            reason="Test assignment",
        )

    def test_assigned_agent_can_list_escalated_conversation(self):
        self.client.force_authenticate(self.assigned_agent)
        response = self.client.get(reverse("staff-conversation-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["ticket_number"], self.ticket.ticket_number)
        self.assertEqual(response.data[0]["customer_email"], self.customer.email)

    def test_unassigned_agent_cannot_list_or_take_over_conversation(self):
        self.client.force_authenticate(self.other_agent)
        listing = self.client.get(reverse("staff-conversation-list"))
        takeover = self.client.post(
            reverse(
                "conversation-takeover",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            format="json",
        )

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data, [])
        self.assertEqual(takeover.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_agent_can_take_over_and_reply(self):
        self.client.force_authenticate(self.assigned_agent)
        takeover = self.client.post(
            reverse(
                "conversation-takeover",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            format="json",
        )

        self.assertEqual(takeover.status_code, status.HTTP_200_OK)
        self.assertEqual(takeover.data["status"], Conversation.Status.AGENT_ACTIVE)

        reply = self.client.post(
            reverse(
                "conversation-human-reply",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "I am reviewing your account now."},
            format="json",
        )

        self.assertEqual(reply.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reply.data["sender_type"], Message.SenderType.AGENT)
        self.assertEqual(reply.data["content"], "I am reviewing your account now.")
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender_user=self.assigned_agent,
                sender_type=Message.SenderType.AGENT,
            ).exists()
        )

    def test_admin_can_take_over_and_reply_as_admin(self):
        self.client.force_authenticate(self.admin)
        takeover = self.client.post(
            reverse(
                "conversation-takeover",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            format="json",
        )
        self.assertEqual(takeover.status_code, status.HTTP_200_OK)

        reply = self.client.post(
            reverse(
                "conversation-human-reply",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "An administrator is handling this request."},
            format="json",
        )

        self.assertEqual(reply.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reply.data["sender_type"], Message.SenderType.ADMIN)
        self.assertEqual(reply.data["content"], "An administrator is handling this request.")

    def test_customer_cannot_access_staff_conversation_list(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse("staff-conversation-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reply_requires_takeover(self):
        self.client.force_authenticate(self.assigned_agent)
        response = self.client.post(
            reverse(
                "conversation-human-reply",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "This should not be accepted yet."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
