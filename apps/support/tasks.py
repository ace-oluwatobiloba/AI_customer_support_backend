import logging
from celery import shared_task
from django.db import DatabaseError, InterfaceError, OperationalError
from apps.support.services import TicketAssignmentError, auto_assign_ticket

logger = logging.getLogger(__name__)

class NoEligibleAgentAvailable(Exception):
    pass
@shared_task(bind=True, name="support.retry_auto_assign_ticket", max_retries=5, default_retry_delay=30)
def retry_auto_assign_ticket(self, ticket_id):
    try:
        assignment = auto_assign_ticket(ticket_id=ticket_id)
    except TicketAssignmentError:
        logger.exception("Ticket %s cannot be automatically assigned.", ticket_id)
        raise
    except (DatabaseError, OperationalError, InterfaceError) as exc:
        logger.exception("Temporary database failure assigning ticket %s.", ticket_id)
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 900))
    if assignment is None:
        exc = NoEligibleAgentAvailable(f"No eligible agent has capacity for ticket {ticket_id}.")
        logger.warning("%s", exc)
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 900))
    return {"ticket_id": str(ticket_id), "assignment_id": str(assignment.pk), "agent_id": str(assignment.agent_id)}
