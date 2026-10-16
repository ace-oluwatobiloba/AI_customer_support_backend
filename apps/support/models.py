import uuid

from django.conf import settings
from django.db import models


class Ticket(models.Model):

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        WAITING_FOR_CUSTOMER = (
            "WAITING_FOR_CUSTOMER",
            "Waiting for Customer",
        )
        ESCALATED = "ESCALATED", "Escalated"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Category(models.TextChoices):
        ACCOUNT = "ACCOUNT", "Account"
        BILLING = "BILLING", "Billing"
        TECHNICAL_SUPPORT = (
            "TECHNICAL_SUPPORT",
            "Technical Support",
        )
        DELIVERY = "DELIVERY", "Delivery"
        CANCELLATION = "CANCELLATION", "Cancellation"
        REFUND = "REFUND", "Refund"
        GENERAL_INQUIRY = (
            "GENERAL_INQUIRY",
            "General Inquiry",
        )
        OTHER = "OTHER", "Other"

    class CreatedSource(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        AGENT = "AGENT", "Agent"
        ADMIN = "ADMIN", "Admin"
        AI = "AI", "AI"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    ticket_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_tickets",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
        blank=True,
        null=True,
    )

    created_source = models.CharField(
        max_length=20,
        choices=CreatedSource.choices,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )

    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.ticket_number} - {self.title}"

class TicketAssignment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="assignments"
    )

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_assignments"
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_ticket_assignments",
        blank=True,
        null=True,
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    unassigned_at = models.DateTimeField(
        blank=True,
        null=True
    )

    reason = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.ticket.ticket_number} → {self.agent.email}"

class TicketEscalation(models.Model):
    class Trigger(models.TextChoices):
        CUSTOMER_REQUEST = (
            "CUSTOMER_REQUEST",
            "Customer Request"
        )
        AI_CONFIDENCE = (
            "AI_CONFIDENCE",
            "AI Confidence"
        )
        BUSINESS_RULE = (
            "BUSINESS_RULE",
            "Business Rule"
        )
        AGENT_REQUEST = (
            "AGENT_REQUEST",
            "Agent Request"
        )
        ADMIN_REQUEST = (
            "ADMIN_REQUEST",
            "Admin Request"
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="escalations"
    )

    # Link the escalation directly to the conversation that caused it.
# The relationship is optional because some escalations may originate
# directly from a ticket rather than from an AI conversation.
    conversation = models.ForeignKey(
    "conversations.Conversation",
    on_delete=models.PROTECT,
    blank=True,
    null=True,
    related_name="escalations",
)

    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_escalations",
        blank=True,
        null=True,
    )

    reason = models.TextField()

    trigger = models.CharField(
        max_length=30,
        choices=Trigger.choices
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True
    )

    resolution_notes = models.TextField(
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"Escalation: {self.ticket.ticket_number}"