import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Records user and system actions for accountability and traceability."""

    # Uses a UUID as the primary key.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Allows system-generated events without a user actor.
    # SET_NULL preserves audit history if the actor's account is deleted.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        blank=True,
        null=True,
    )

    # Identifies the action and the entity affected by it.
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(
        blank=True,
        null=True,
    )

    # Stores optional structured information about the event.
    metadata = models.JSONField(
        blank=True,
        null=True,
    )

    # Captures request information when available.
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
    )

    # Records when the audit event occurred.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Displays the newest audit events first.
        ordering = ["-created_at"]

    def __str__(self):
        # Provides a readable description in the Django admin and logs.
        return f"{self.action} - {self.entity_type}"