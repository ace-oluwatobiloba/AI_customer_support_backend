import re

from django.db import transaction

from apps.conversations.models import Conversation
from apps.support.models import Ticket, TicketEscalation
from apps.support.services import (
    create_customer_ticket,
    escalate_ticket,
)


ESCALATION_PATTERNS = (
    r"\b(?:speak|talk|connect|transfer|escalate)\b.{0,60}"
    r"\b(?:human|agent|representative|support staff|person)\b",
    r"\b(?:human|agent|representative|support staff)\b.{0,60}"
    r"\b(?:please|help|connect|escalate|transfer|need|want)\b",
)


def customer_requested_escalation(message):
    """Return whether the message explicitly requests human assistance."""
    if not isinstance(message, str):
        return False

    return any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in ESCALATION_PATTERNS
    )


@transaction.atomic
def escalate_conversation(*, conversation_id, customer, reason):
    """Create/reuse a ticket, record escalation, and attempt assignment."""
    conversation = (
        Conversation.objects
        .select_for_update()
        .get(id=conversation_id, customer=customer)
    )

    if conversation.status in (
        Conversation.Status.RESOLVED,
        Conversation.Status.CLOSED,
    ):
        raise ValueError("This conversation is already closed.")

    ticket = conversation.ticket

    if ticket is None:
        ticket = create_customer_ticket(
            customer=customer,
            title=f"Support escalation: {conversation.title}",
            description=reason,
            category=Ticket.Category.ACCOUNT,
        )
        conversation.ticket = ticket

    existing_escalation = TicketEscalation.objects.filter(
        ticket=ticket,
        conversation=conversation,
        trigger=TicketEscalation.Trigger.CUSTOMER_REQUEST,
    ).first()

    if existing_escalation is None:
        escalate_ticket(
            ticket_id=ticket.id,
            escalated_by=None,
            reason=reason,
            trigger=TicketEscalation.Trigger.CUSTOMER_REQUEST,
            conversation=conversation,
        )

    conversation.status = Conversation.Status.ESCALATED
    conversation.save(update_fields=["ticket", "status", "updated_at"])

    # Queue assignment after the escalation transaction commits.
    def enqueue_assignment(ticket_id=ticket.id):
        from apps.support.tasks import retry_auto_assign_ticket
        try:
            retry_auto_assign_ticket.delay(str(ticket_id))
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not queue automated assignment for ticket %s.", ticket_id
            )

    transaction.on_commit(enqueue_assignment)
    return ticket
