"""Read-only API serializers for user notifications."""

from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Expose notification content and read state without delivery internals."""

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "title",
            "message",
            "read_at",
            "created_at",
        )
        read_only_fields = fields
