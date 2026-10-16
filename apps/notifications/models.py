import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Stores notifications delivered to users."""

    # Defines the supported notification event types.
    class Type(models.TextChoices):
        TICKET_CREATED = "TICKET_CREATED", "Ticket Created"
        TICKET_UPDATED = "TICKET_UPDATED", "Ticket Updated"
        TICKET_ASSIGNED = "TICKET_ASSIGNED", "Ticket Assigned"
        TICKET_ESCALATED = "TICKET_ESCALATED", "Ticket Escalated"
        TICKET_RESOLVED = "TICKET_RESOLVED", "Ticket Resolved"
        AGENT_REPLY = "AGENT_REPLY", "Agent Reply"
        SYSTEM_ALERT = "SYSTEM_ALERT", "System Alert"

    # Uses a UUID as the primary key.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Identifies the user receiving the notification.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # Identifies the event that triggered the notification.
    notification_type = models.CharField(
        max_length=50,
        choices=Type.choices,
    )

    # Stores the notification heading and message.
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Remains NULL until the user reads the notification.
    read_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # Records when the notification was created.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        # Provides a readable representation in Django admin and logs.
        return f"{self.notification_type}: {self.title}"


class NotificationDelivery(models.Model):
    """Tracks individual attempts to deliver a notification."""

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"

    class Provider(models.TextChoices):
        RESEND = "RESEND", "Resend"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    # Uses a UUID as the primary key.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Deletes delivery records when their parent notification is deleted.
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    # Records the delivery channel and provider.
    channel = models.CharField(
        max_length=30,
        choices=Channel.choices,
        default=Channel.EMAIL,
    )
    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
        default=Provider.RESEND,
    )

    # Tracks the current delivery outcome and retry count.
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)

    # Records delivery timestamps and any failure details.
    sent_at = models.DateTimeField(blank=True, null=True)
    failed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        # Makes delivery records easier to identify during debugging.
        return f"{self.channel} delivery: {self.status}"