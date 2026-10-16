from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import (
    Conversation,
    Message,
    MessageRevision,
)

from apps.support.models import (
    Ticket,
    TicketEscalation,
)


# get_user_model() ensures the tests use our custom User model
# configured through AUTH_USER_MODEL instead of Django's default user.
User = get_user_model()


class ConversationModelTest(TestCase):
    """
    Tests the Conversation model independently.

    These tests verify that a conversation correctly belongs to a customer
    and can optionally be connected to a support ticket.
    """

    def setUp(self):
        # Create the customer who owns the conversation.
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        # Create a ticket that can later be associated with the conversation.
        self.ticket = Ticket.objects.create(
            ticket_number="TKT-20261008-1001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Unable to access account",
            description="Customer cannot access their account.",
            priority=Ticket.Priority.MEDIUM,
            category=Ticket.Category.ACCOUNT,
        )

    def test_create_conversation_without_ticket(self):
        """
        A conversation can begin before a formal support ticket exists.
        """

        conversation = Conversation.objects.create(
            customer=self.customer,
            title="Account access problem",
        )

        self.assertEqual(
            conversation.customer,
            self.customer,
        )

        self.assertIsNone(
            conversation.ticket,
        )

        self.assertEqual(
            conversation.status,
            Conversation.Status.ACTIVE,
        )

    def test_conversation_can_be_linked_to_ticket(self):
        """
        Once a support case is created, the conversation can be linked
        to that ticket.
        """

        conversation = Conversation.objects.create(
            customer=self.customer,
            ticket=self.ticket,
            title="Account access problem",
        )

        self.assertEqual(
            conversation.ticket,
            self.ticket,
        )

        # OneToOneField creates the reverse relationship:
        # ticket.conversation
        self.assertEqual(
            self.ticket.conversation,
            conversation,
        )

    def test_conversation_timestamps_are_created(self):
        """Verify Django automatically creates lifecycle timestamps."""

        conversation = Conversation.objects.create(
            customer=self.customer,
            title="Test conversation",
        )

        self.assertIsNotNone(
            conversation.started_at,
        )

        self.assertIsNotNone(
            conversation.created_at,
        )

        self.assertIsNotNone(
            conversation.updated_at,
        )


class MessageModelTest(TestCase):
    """
    Tests individual messages and their relationship to conversations.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        self.conversation = Conversation.objects.create(
            customer=self.customer,
            title="Technical support conversation",
        )

    def test_create_customer_message(self):
        """A customer message should belong to the conversation."""

        message = Message.objects.create(
            conversation=self.conversation,
            sender_user=self.customer,
            sender_type=Message.SenderType.CUSTOMER,
            content="I cannot log into my account.",
        )

        self.assertEqual(
            message.conversation,
            self.conversation,
        )

        self.assertEqual(
            message.sender_user,
            self.customer,
        )

        self.assertEqual(
            message.sender_type,
            Message.SenderType.CUSTOMER,
        )

        self.assertEqual(
            message.content,
            "I cannot log into my account.",
        )

    def test_create_ai_message(self):
        """
        AI messages can exist without a human sender.

        The model stores the AI provider/model separately so we can
        identify which model generated a response later.
        """

        message = Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.AI,
            content="I can help you recover your account.",
            model="gpt-5.6",
            metadata={
                "source": "ai",
                "test": True,
            },
        )

        self.assertIsNone(
            message.sender_user,
        )

        self.assertEqual(
            message.sender_type,
            Message.SenderType.AI,
        )

        self.assertEqual(
            message.model,
            "gpt-5.6",
        )

        self.assertEqual(
            message.metadata["source"],
            "ai",
        )

    def test_conversation_can_have_multiple_messages(self):
        """
        A conversation should be able to contain multiple messages
        from different participants.
        """

        Message.objects.create(
            conversation=self.conversation,
            sender_user=self.customer,
            sender_type=Message.SenderType.CUSTOMER,
            content="Hello.",
        )

        Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.AI,
            content="Hello. How can I help?",
            model="gpt-5.6",
        )

        self.assertEqual(
            self.conversation.messages.count(),
            2,
        )


class MessageRevisionModelTest(TestCase):
    """
    Tests message editing/history.

    A revision preserves the previous message content instead of
    destroying the original version.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        self.conversation = Conversation.objects.create(
            customer=self.customer,
            title="Message revision test",
        )

        self.message = Message.objects.create(
            conversation=self.conversation,
            sender_user=self.customer,
            sender_type=Message.SenderType.CUSTOMER,
            content="Please cancel my order.",
        )

    def test_create_message_revision(self):
        """A previous version of a message can be preserved."""

        revision = MessageRevision.objects.create(
            message=self.message,
            revised_by=self.customer,
            previous_content="Please cancel my order.",
            revision_number=1,
        )

        self.assertEqual(
            revision.message,
            self.message,
        )

        self.assertEqual(
            revision.revised_by,
            self.customer,
        )

        self.assertEqual(
            revision.previous_content,
            "Please cancel my order.",
        )

        self.assertEqual(
            revision.revision_number,
            1,
        )

    def test_message_can_have_multiple_revisions(self):
        """
        A message may be edited multiple times, with every previous
        version preserved as a separate revision.
        """

        MessageRevision.objects.create(
            message=self.message,
            revised_by=self.customer,
            previous_content="Please cancel my order.",
            revision_number=1,
        )

        MessageRevision.objects.create(
            message=self.message,
            revised_by=self.customer,
            previous_content=(
                "Please cancel my order and issue a refund."
            ),
            revision_number=2,
        )

        self.assertEqual(
            self.message.revisions.count(),
            2,
        )

        # The model Meta.ordering should return the newest revision first.
        latest_revision = self.message.revisions.first()

        self.assertEqual(
            latest_revision.revision_number,
            2,
        )

    def test_revision_number_must_be_unique_per_message(self):
        """
        Two revisions for the same message cannot have the same number.
        """

        MessageRevision.objects.create(
            message=self.message,
            revised_by=self.customer,
            previous_content="Original content.",
            revision_number=1,
        )

        # The database-level unique constraint should reject another
        # revision with the same message + revision number.
        with self.assertRaises(Exception):
            MessageRevision.objects.create(
                message=self.message,
                revised_by=self.customer,
                previous_content="Another version.",
                revision_number=1,
            )


class ConversationSupportIntegrationTest(TestCase):
    """
    Integration test connecting Accounts, Support, and Conversations.

    This represents an important real-world workflow:

        Customer
            ↓
        Conversation
            ↓
        Ticket
            ↓
        Escalation
    """

    def setUp(self):
        # Customer initiates the support conversation.
        self.customer = User.objects.create_user(
            email="customer@support.com",
            password="CustomerPass123!",
            role=User.Role.CUSTOMER,
        )

        # Agent represents the human support representative.
        self.agent = User.objects.create_user(
            email="agent@support.com",
            password="AgentPass123!",
            role=User.Role.AGENT,
        )

        # Admin represents the user capable of managing/escalating
        # support operations.
        self.admin = User.objects.create_superuser(
            email="admin@support.com",
            password="AdminPass123!",
        )

    def test_complete_conversation_to_escalation_workflow(self):
        """
        Test the complete relationship between the implemented domains.
        """

        # ---------------------------------------------------------
        # STEP 1: Customer starts an AI/support conversation.
        # ---------------------------------------------------------
        conversation = Conversation.objects.create(
            customer=self.customer,
            title="Unable to access account",
        )

        self.assertEqual(
            conversation.customer,
            self.customer,
        )

        self.assertEqual(
            conversation.status,
            Conversation.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # STEP 2: Customer sends a message.
        # ---------------------------------------------------------
        customer_message = Message.objects.create(
            conversation=conversation,
            sender_user=self.customer,
            sender_type=Message.SenderType.CUSTOMER,
            content="I cannot log into my account.",
        )

        self.assertEqual(
            conversation.messages.count(),
            1,
        )

        # ---------------------------------------------------------
        # STEP 3: AI responds.
        # ---------------------------------------------------------
        ai_message = Message.objects.create(
            conversation=conversation,
            sender_type=Message.SenderType.AI,
            content="I can help you recover your account.",
            model="gpt-5.6",
            metadata={
                "intent": "ACCOUNT",
                "confidence": 0.91,
            },
        )

        self.assertEqual(
            conversation.messages.count(),
            2,
        )

        self.assertEqual(
            ai_message.model,
            "gpt-5.6",
        )

        # ---------------------------------------------------------
        # STEP 4: Customer requests human assistance.
        # A formal support ticket is created.
        # ---------------------------------------------------------
        ticket = Ticket.objects.create(
            ticket_number="TKT-20261008-2001",
            customer=self.customer,
            created_by=self.customer,
            created_source=Ticket.CreatedSource.CUSTOMER,
            title="Unable to access account",
            description="Customer cannot log into their account.",
            priority=Ticket.Priority.HIGH,
            category=Ticket.Category.ACCOUNT,
        )

        # Connect the existing conversation to the new ticket.
        conversation.ticket = ticket
        conversation.save()

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.ticket,
            ticket,
        )

        # ---------------------------------------------------------
        # STEP 5: Agent takes over.
        # ---------------------------------------------------------
        ticket.status = Ticket.Status.ESCALATED
        ticket.save()

        conversation.status = Conversation.Status.ESCALATED
        conversation.save()

        # ---------------------------------------------------------
        # STEP 6: Record the escalation event.
        # ---------------------------------------------------------
        escalation = TicketEscalation.objects.create(
            ticket=ticket,
            conversation=conversation,
            escalated_by=self.agent,
            reason="Customer requested human assistance.",
            trigger=TicketEscalation.Trigger.CUSTOMER_REQUEST,
        )

        # ---------------------------------------------------------
        # STEP 7: Verify the complete relationship chain.
        # ---------------------------------------------------------

        self.assertEqual(
            escalation.ticket,
            ticket,
        )

        self.assertEqual(
            escalation.conversation,
            conversation,
        )

        self.assertEqual(
            escalation.escalated_by,
            self.agent,
        )

        self.assertEqual(
            escalation.trigger,
            TicketEscalation.Trigger.CUSTOMER_REQUEST,
        )

        self.assertEqual(
            ticket.conversation,
            conversation,
        )

        self.assertEqual(
            conversation.escalations.count(),
            1,
        )

        self.assertEqual(
            ticket.escalations.count(),
            1,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.ESCALATED,
        )

        self.assertEqual(
            conversation.status,
            Conversation.Status.ESCALATED,
        )

        # Make sure the original customer message still exists.
        self.assertTrue(
            Message.objects.filter(
                id=customer_message.id
            ).exists()
        )