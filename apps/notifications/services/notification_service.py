"""Centralized in-app notification and email-delivery services.

Notifications are persisted in the caller's transaction. Optional email
delivery is scheduled with transaction.on_commit so a provider failure cannot
roll back the business operation or remove the in-app notification.
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.email_delivery import (
    EmailDeliveryError,
    send_mail,
)
from apps.notifications.models import Notification, NotificationDelivery

logger = logging.getLogger(__name__)


def create_notification(
    *,
    user,
    notification_type,
    title,
    message,
    send_email=False,
    html_message=None,
):
    """Create an in-app notification and optionally schedule email delivery.

    The notification and its PENDING delivery record are created together.
    Email is attempted only after the surrounding database transaction commits.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        raise ValidationError("A saved authenticated notification recipient is required.")
    if not getattr(user, "pk", None) or user._state.adding:
        raise ValidationError("The notification recipient must already be saved.")

    valid_types = {choice[0] for choice in Notification.Type.choices}
    if notification_type not in valid_types:
        raise ValidationError("The notification type is invalid.")

    if not isinstance(title, str) or not title.strip():
        raise ValidationError("A notification title is required.")
    if len(title.strip()) > 255:
        raise ValidationError("Notification title must be 255 characters or fewer.")
    if not isinstance(message, str) or not message.strip():
        raise ValidationError("A notification message is required.")

    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title.strip(),
        message=message.strip(),
    )

    if send_email:
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=NotificationDelivery.Channel.EMAIL,
            provider=NotificationDelivery.Provider.RESEND,
            status=NotificationDelivery.Status.PENDING,
        )
        def enqueue_delivery(delivery_id=delivery.pk, html=html_message):
            from apps.notifications.tasks import deliver_notification_email_task
            try:
                deliver_notification_email_task.delay(delivery_id=str(delivery_id), html_message=html)
            except Exception:
                logger.exception("Could not queue notification delivery %s.", delivery_id)

        transaction.on_commit(enqueue_delivery)

    return notification


def create_notifications(*, users, notification_type, title, message,
                         send_email=False):
    """Create the same notification for each distinct saved recipient."""
    notifications = []
    seen_ids = set()
    for user in users:
        if user.pk in seen_ids:
            continue
        seen_ids.add(user.pk)
        notifications.append(
            create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                send_email=send_email,
            )
        )
    return notifications


def deliver_notification_email(*, delivery_id, html_message=None):
    """Attempt one Resend delivery and persist its final outcome.

    Provider errors are recorded and swallowed deliberately: the in-app
    notification remains available and the business transaction is unaffected.
    """
    with transaction.atomic():
        try:
            delivery = (
                NotificationDelivery.objects.select_for_update()
                .select_related("notification__user")
                .get(pk=delivery_id)
            )
        except NotificationDelivery.DoesNotExist:
            logger.warning("Notification delivery record was not found.")
            return None

        if delivery.status == NotificationDelivery.Status.SENT:
            return delivery

        delivery.attempt_count += 1
        delivery.status = NotificationDelivery.Status.PENDING
        delivery.failed_at = None
        delivery.error_message = None
        delivery.save(update_fields=[
            "attempt_count", "status", "failed_at", "error_message", "updated_at"
        ])

        notification = delivery.notification
        recipient = notification.user.email
        subject = notification.title
        body = notification.message

    try:
        sent_count = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
            html_message=html_message,
        )
        if sent_count != 1:
            raise EmailDeliveryError("The provider did not accept the message.")
    except Exception as exc:
        # Persist only a safe, generic error; never store provider payloads,
        # credentials, message bodies, or recipient addresses in error logs.
        with transaction.atomic():
            failed = NotificationDelivery.objects.select_for_update().get(
                pk=delivery_id
            )
            failed.status = NotificationDelivery.Status.FAILED
            failed.failed_at = timezone.now()
            failed.error_message = "Email provider did not accept the message."
            failed.save(update_fields=[
                "status", "failed_at", "error_message", "updated_at"
            ])
        logger.warning(
            "Notification email delivery failed (exception_type=%s).",
            type(exc).__name__,
        )
        return failed

    with transaction.atomic():
        sent = NotificationDelivery.objects.select_for_update().get(
            pk=delivery_id
        )
        sent.status = NotificationDelivery.Status.SENT
        sent.sent_at = timezone.now()
        sent.failed_at = None
        sent.error_message = None
        sent.save(update_fields=[
            "status", "sent_at", "failed_at", "error_message", "updated_at"
        ])
    return sent
