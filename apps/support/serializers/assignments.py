"""
Serializers for ticket assignment operations.
"""

from rest_framework import serializers

from apps.accounts.models import User
from apps.support.models import TicketAssignment


class TicketAssignmentCreateSerializer(serializers.Serializer):
    """
    Validate an assignment or reassignment request.
    """

    agent_id = serializers.UUIDField()

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )

    def validate_agent_id(self, value):
        agent_exists = User.objects.filter(
            id=value,
            role=User.Role.AGENT,
            is_active=True,
            status=User.Status.ACTIVE,
        ).exists()

        if not agent_exists:
            raise serializers.ValidationError(
                "The selected account is not an eligible active agent."
            )

        return value


class TicketAssignmentSerializer(serializers.ModelSerializer):
    """
    Read-only representation of an assignment record.
    """

    agent_email = serializers.EmailField(
        source="agent.email",
        read_only=True,
    )

    assigned_by_email = serializers.EmailField(
        source="assigned_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = TicketAssignment

        fields = [
            "id",
            "ticket",
            "agent",
            "agent_email",
            "assigned_by",
            "assigned_by_email",
            "assigned_at",
            "unassigned_at",
            "reason",
        ]

        read_only_fields = fields