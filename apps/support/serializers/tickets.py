"""
Serializers for support tickets.
"""

from rest_framework import serializers

from apps.support.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    """
    Serialize ticket data while protecting server-managed fields.
    """

    customer_email = serializers.EmailField(
        source="customer.email",
        read_only=True,
    )

    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Ticket

        fields = [
            "id",
            "ticket_number",
            "customer",
            "customer_email",
            "created_by",
            "created_by_email",
            "created_source",
            "title",
            "description",
            "status",
            "priority",
            "category",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "ticket_number",
            "customer",
            "customer_email",
            "created_by",
            "created_by_email",
            "created_source",
            "status",
            "priority",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]