from rest_framework import serializers

from apps.conversations.models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = (
            "id",
            "title",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "created_at",
            "updated_at",
        )


class CreateConversationSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )


class CreateMessageSerializer(serializers.Serializer):
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=10000,
    )


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = (
            "id",
            "sender_type",
            "content",
            "metadata",
            "created_at",
        )
        read_only_fields = fields

class ConversationMessageResponseSerializer(serializers.Serializer):
    customer_message = MessageSerializer()
    assistant_message = MessageSerializer()


class ConversationEscalationResponseSerializer(
    ConversationMessageResponseSerializer
):
    ticket_number = serializers.CharField()
    escalated = serializers.BooleanField()


class ConversationMessageErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    customer_message = MessageSerializer(required=False)

class StaffConversationSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField(read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    ticket_number = serializers.CharField(
        source="ticket.ticket_number", read_only=True
    )

    class Meta:
        model = Conversation
        fields = (
            "id",
            "title",
            "status",
            "customer_id",
            "customer_email",
            "ticket_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class HumanReplySerializer(serializers.Serializer):
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=10000,
    )
