import logging
from django.db import transaction
from django.shortcuts import get_object_or_404, render

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)

from apps.accounts.models import User
from apps.conversations.models import Conversation, Message

from apps.conversations.serial.serializers import (
    ConversationSerializer,
    CreateConversationSerializer,
    CreateMessageSerializer,
    MessageSerializer,
    ConversationMessageResponseSerializer,
    ConversationEscalationResponseSerializer,
    ConversationMessageErrorSerializer,
    StaffConversationSerializer,
    HumanReplySerializer,
)

from apps.conversations.services.handover_service import (
    ConversationHandoverError,
    staff_conversation_queryset,
    take_over_conversation,
    create_human_reply,
)

from apps.conversations.services.escalation_service import (
    customer_requested_escalation,
    escalate_conversation,
)

from apps.knowledge.services.rag_service import (
    RAGServiceError,
    answer_question,
)

logger = logging.getLogger(__name__)

@extend_schema_view(
    get=extend_schema(
        operation_id="conversation_list",
        responses={200: ConversationSerializer(many=True)},
    ),
    post=extend_schema(
        operation_id="conversation_create",
        request=CreateConversationSerializer,
        responses={201: ConversationSerializer},
    ),
)

class ConversationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = Conversation.objects.filter(
            customer=request.user
        ).order_by("-created_at")

        serializer = ConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        title = serializer.validated_data.get("title", "").strip()
        if not title:
            title = "Support conversation"

        conversation = Conversation.objects.create(
            customer=request.user,
            title=title,
        )

        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED,
        )

@extend_schema_view(
    get=extend_schema(
        operation_id="conversation_detail",
        responses={200: ConversationSerializer},
    ),
)

class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            pk=conversation_id,
            customer=request.user,
        )

        return Response(ConversationSerializer(conversation).data)

@extend_schema_view(
    get=extend_schema(
        operation_id="conversation_messages_list",
        responses={200: MessageSerializer(many=True)},
    ),
    post=extend_schema(
        operation_id="conversation_message_create",
        request=CreateMessageSerializer,
        responses={
            201: PolymorphicProxySerializer(
                component_name="ConversationMessageSuccess",
                serializers=[
                    ConversationMessageResponseSerializer,
                    ConversationEscalationResponseSerializer,
                ],
                resource_type_field_name=None,
           ),
           409: ConversationMessageErrorSerializer,
           503: ConversationMessageErrorSerializer,
       },
    ),
)

class ConversationMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        return get_object_or_404(
            Conversation,
            pk=conversation_id,
            customer=request.user,
        )

    def get(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)

        messages = conversation.messages.order_by("created_at")
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, conversation_id):
        conversation = self.get_conversation(request, conversation_id)

        serializer = CreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data["content"]

        # Only active conversations can receive AI-generated responses.
        if conversation.status != Conversation.Status.ACTIVE:
            return Response(
                {
                    "detail": (
                        "This conversation is not active for AI responses. "
                        "Please continue through the assigned support agent "
                        "or open a new conversation."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Persist the customer's message before calling the external AI service.
        with transaction.atomic():
            customer_message = Message.objects.create(
                conversation=conversation,
                sender_user=request.user,
                sender_type=Message.SenderType.CUSTOMER,
                content=content,
            )

            if customer_requested_escalation(content):
                try:
                    ticket = escalate_conversation(
                        conversation_id=conversation.id,
                        customer=request.user,
                        reason=content,
                    )
                except Exception:
                    logger.exception(
                        "Escalation failed for conversation %s",
                        conversation.pk,
                    )
                    return Response(
                        {
                            "detail": (
                                "Your message was saved, but we could not "
                                "complete the escalation. Please try again."
                            ),
                            "customer_message": MessageSerializer(
                                customer_message
                            ).data,
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )

                assistant_message = Message.objects.create(
                    conversation=conversation,
                    sender_user=None,
                    sender_type=Message.SenderType.AI,
                    content=(
                        "Your request has been escalated to our support "
                        f"team. Your ticket number is {ticket.ticket_number}. "
                        "A human agent will need to review your issue."
                    ),
                    metadata={
                        "ticket_number": ticket.ticket_number,
                        "escalated": True,
                    },
                )

                return Response(
                    {
                        "customer_message": MessageSerializer(
                            customer_message
                        ).data,
                        "assistant_message": MessageSerializer(
                            assistant_message
                        ).data,
                        "ticket_number": ticket.ticket_number,
                        "escalated": True,
                    },
                    status=status.HTTP_201_CREATED,
               )

        try:
            result = answer_question(content)
        except RAGServiceError:
            logger.exception(
                "RAG pipeline failed for conversation %s",
                conversation.pk,
            )
            return Response(
               {
                   "detail": (
                       "Your message was saved, but an answer could not "
                       "be generated. Please try again later or contact "
                       "a support agent."
                    ),
                    "customer_message": MessageSerializer(
                        customer_message
                    ).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
           )

        assistant_message = Message.objects.create(
            conversation=conversation,
            sender_user=None,
            sender_type=Message.SenderType.AI,
            content=result["answer"],
            metadata={"sources": result["sources"]},
        )

        return Response(
            {
                "customer_message": MessageSerializer(
                    customer_message
                ).data,
                "assistant_message": MessageSerializer(
                    assistant_message
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

def chat_page(request):
    return render(request, "conversations/chat.html")

class StaffConversationListView(APIView):
    """List escalated and human-active conversations visible to staff."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="staff_conversation_list",
        responses={200: StaffConversationSerializer(many=True)},
        tags=["Staff Conversations"],
    )
    def get(self, request):
        if not (
            request.user.is_active
            and request.user.status == User.Status.ACTIVE
            and request.user.role in (User.Role.AGENT, User.Role.ADMIN)
        ):
            return Response(
                {"detail": "Active agent or administrator access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        conversations = staff_conversation_queryset(request.user)
        return Response(
            StaffConversationSerializer(conversations, many=True).data
        )


class ConversationTakeoverView(APIView):
    """Allow the assigned agent or an administrator to take over."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="conversation_takeover",
        responses={200: ConversationSerializer},
        tags=["Staff Conversations"],
    )
    def post(self, request, conversation_id):
        try:
            conversation = take_over_conversation(
                conversation_id=conversation_id,
                actor=request.user,
            )
        except ConversationHandoverError as exc:
            message = str(exc)
            if message == "Conversation not found.":
                code = status.HTTP_404_NOT_FOUND
            elif "Only escalated conversations" in message:
                code = status.HTTP_409_CONFLICT
            else:
                code = status.HTTP_403_FORBIDDEN
            return Response({"detail": message}, status=code)

        return Response(ConversationSerializer(conversation).data)


class HumanConversationReplyView(APIView):
    """Create a human agent/admin reply in a taken-over conversation."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="conversation_human_reply",
        request=HumanReplySerializer,
        responses={201: MessageSerializer},
        tags=["Staff Conversations"],
    )
    def post(self, request, conversation_id):
        serializer = HumanReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = create_human_reply(
                conversation_id=conversation_id,
                actor=request.user,
                content=serializer.validated_data["content"],
            )
        except ConversationHandoverError as exc:
            message_text = str(exc)
            if message_text == "Conversation not found.":
                code = status.HTTP_404_NOT_FOUND
            elif "Take over" in message_text:
                code = status.HTTP_409_CONFLICT
            else:
                code = status.HTTP_403_FORBIDDEN
            return Response({"detail": message_text}, status=code)

        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )
