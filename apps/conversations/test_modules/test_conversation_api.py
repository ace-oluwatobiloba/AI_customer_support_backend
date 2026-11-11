from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.conversations.models import Conversation, Message
from apps.support.models import TicketEscalation

from apps.conversations.services.escalation_service import (
    escalate_conversation,
)

class ConversationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.customer = User.objects.create_user(
            email="customer1@example.com",
            password="Test-password-123!",
        )
        cls.other_customer = User.objects.create_user(
            email="customer2@example.com",
            password="Test-password-123!",
        )

        cls.conversation = Conversation.objects.create(
            customer=cls.customer,
            title="Account support",
        )
        cls.other_conversation = Conversation.objects.create(
            customer=cls.other_customer,
            title="Private conversation",
        )

    def setUp(self):
        self.client.force_authenticate(user=self.customer)

    def test_anonymous_user_cannot_list_conversations(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(
            reverse("conversation-list-create")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_customer_only_sees_own_conversations(self):
        response = self.client.get(
            reverse("conversation-list-create")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_ids = {item["id"] for item in response.data}
        self.assertIn(str(self.conversation.pk), returned_ids)
        self.assertNotIn(str(self.other_conversation.pk), returned_ids)

    def test_customer_can_create_conversation(self):
        response = self.client.post(
            reverse("conversation-list-create"),
            {"title": "Order enquiry"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["title"], "Order enquiry")
        self.assertTrue(
            Conversation.objects.filter(
                pk=response.data["id"],
                customer=self.customer,
            ).exists()
        )

    def test_customer_can_create_conversation_without_title(self):
        response = self.client.post(
            reverse("conversation-list-create"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["title"], "Support conversation")

    def test_customer_cannot_read_another_customers_conversation(self):
        response = self.client.get(
            reverse(
                "conversation-detail",
                kwargs={"conversation_id": self.other_conversation.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_read_another_customers_messages(self):
        response = self.client.get(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.other_conversation.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_message_content_must_not_be_blank(self):
        response = self.client.post(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "   "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("apps.conversations.views.answer_question")
    def test_post_message_saves_customer_and_ai_messages(
        self,
        mock_answer_question,
    ):
        mock_answer_question.return_value = {
            "answer": "You can update your account settings.",
            "sources": [
                {
                    "document_title": "Account Help",
                    "version_number": 2,
                    "chunk_index": 4,
                }
            ],
        }

        response = self.client.post(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "How do I update my account?"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["customer_message"]["content"],
            "How do I update my account?",
        )
        self.assertEqual(
            response.data["customer_message"]["sender_type"],
            Message.SenderType.CUSTOMER,
        )
        self.assertEqual(
            response.data["assistant_message"]["content"],
            "You can update your account settings.",
        )
        self.assertEqual(
            response.data["assistant_message"]["sender_type"],
            Message.SenderType.AI,
        )
        self.assertEqual(
            response.data["assistant_message"]["metadata"]["sources"],
            mock_answer_question.return_value["sources"],
        )

        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation
            ).count(),
            2,
        )
        mock_answer_question.assert_called_once_with(
            "How do I update my account?"
        )

    @patch("apps.conversations.views.answer_question")
    def test_rag_failure_keeps_customer_message(
        self,
        mock_answer_question,
    ):
        from apps.knowledge.services.rag_service import RAGServiceError

        mock_answer_question.side_effect = RAGServiceError(
            "Simulated retrieval failure"
        )

        response = self.client.post(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": "I need help with my account."},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.CUSTOMER,
                content="I need help with my account.",
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.AI,
            ).exists()
        )

    def test_escalated_conversation_rejects_ai_message(self):
        self.conversation.status = Conversation.Status.ESCALATED
        self.conversation.save(update_fields=["status"])

        with patch("apps.conversations.views.answer_question") as mock_answer:
            response = self.client.post(
                reverse(
                    "conversation-messages",
                    kwargs={"conversation_id": self.conversation.pk},
                ),
                {"content": "I need more help."},
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        mock_answer.assert_not_called()
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation
            ).count(),
            0,
        )

    @patch("apps.conversations.views.answer_question")
    def test_customer_can_request_human_escalation(
        self,
        mock_answer_question,
    ):
        message = "Please escalate this issue to a human support agent."

        response = self.client.post(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": message},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(response.data["escalated"])
        self.assertTrue(response.data["ticket_number"].startswith("TKT-"))

        self.conversation.refresh_from_db()

        self.assertEqual(
            self.conversation.status,
            Conversation.Status.ESCALATED,
        )
        self.assertIsNotNone(self.conversation.ticket_id)
        self.assertEqual(
            self.conversation.ticket.ticket_number,
            response.data["ticket_number"],
        )
        self.assertEqual(
            self.conversation.ticket.status,
            "ESCALATED",
        )
        self.assertEqual(
            self.conversation.escalations.count(),
            1,
        )
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.CUSTOMER,
                content=message,
            ).exists()
        )
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.AI,
                metadata__escalated=True,
            ).exists()
        )
        mock_answer_question.assert_not_called()

    def test_repeated_escalation_does_not_duplicate_escalation_record(self):
        from apps.conversations.services.escalation_service import (
            escalate_conversation,
        )

        first_ticket = escalate_conversation(
            conversation_id=self.conversation.pk,
            customer=self.customer,
            reason="Please connect me to a human agent.",
        )
        second_ticket = escalate_conversation(
            conversation_id=self.conversation.pk,
            customer=self.customer,
            reason="I still need a human agent.",
        )

        self.assertEqual(first_ticket.pk, second_ticket.pk)
        self.assertEqual(
            TicketEscalation.objects.filter(
                ticket=first_ticket,
                conversation=self.conversation,
                trigger=TicketEscalation.Trigger.CUSTOMER_REQUEST,
            ).count(),
            1,
        )

    @patch("apps.conversations.views.escalate_conversation")
    @patch("apps.conversations.views.answer_question")
    def test_escalation_failure_keeps_customer_message(
        self,
        mock_answer_question,
        mock_escalate_conversation,
    ):
        mock_escalate_conversation.side_effect = RuntimeError(
            "Simulated escalation failure"
        )
        message = "Please connect me to a human support agent."

        response = self.client.post(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            ),
            {"content": message},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.CUSTOMER,
                content=message,
            ).exists()
        )
        self.assertFalse(
            Message.objects.filter(
                conversation=self.conversation,
                sender_type=Message.SenderType.AI,
            ).exists()
        )
        mock_answer_question.assert_not_called()

    def test_customer_can_list_conversation_messages(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender_user=self.customer,
            sender_type=Message.SenderType.CUSTOMER,
            content="Previous question",
        )

        response = self.client.get(
            reverse(
                "conversation-messages",
                kwargs={"conversation_id": self.conversation.pk},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(message.pk))
        self.assertEqual(response.data[0]["content"], "Previous question")
