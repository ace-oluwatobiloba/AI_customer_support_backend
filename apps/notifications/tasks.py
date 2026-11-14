import logging
from celery import shared_task
from apps.notifications.models import NotificationDelivery
from apps.notifications.services.notification_service import deliver_notification_email
logger = logging.getLogger(__name__)
@shared_task(bind=True, name="notifications.deliver_email", max_retries=3, default_retry_delay=60)
def deliver_notification_email_task(self, delivery_id, html_message=None):
    delivery = deliver_notification_email(delivery_id=delivery_id, html_message=html_message)
    if delivery is None:
        return {"delivery_id": str(delivery_id), "status": "not_found"}
    if delivery.status == NotificationDelivery.Status.FAILED:
        logger.warning("Notification delivery %s failed; retrying.", delivery_id)
        raise self.retry(exc=RuntimeError("Notification email delivery failed."))
    return {"delivery_id": str(delivery_id), "status": delivery.status}
