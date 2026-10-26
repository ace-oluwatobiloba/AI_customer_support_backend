"""
Serializers for ticket escalation requests and responses.
"""

from rest_framework import serializers

from apps.support.models import TicketEscalation


class TicketEscalationCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=5000,
    )

    trigger = serializers.ChoiceField(
        choices=TicketEscalation.Trigger.choices,
    )

    conversation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "An escalation reason is required."
            )

        return value.strip()


class TicketEscalationSerializer(serializers.ModelSerializer):
    escalated_by_email = serializers.EmailField(
        source="escalated_by.email",
        read_only=True,
        allow_null=True,
    )

    conversation_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = TicketEscalation
        fields = [
            "id",
            "ticket",
            "conversation_id",
            "escalated_by",
            "escalated_by_email",
            "reason",
            "trigger",
            "created_at",
            "resolved_at",
            "resolution_notes",
        ]
        read_only_fields = fields