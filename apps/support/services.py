"""
Business services for support ticket management.
"""

import secrets
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.support.models import (
    Ticket,
    TicketAssignment,
    TicketEscalation,
)

def generate_ticket_number():
    """
    Generate a ticket number.

    Example: TKT-20261016-A1B2C3D4

    The database unique constraint remains the final
    guarantee of uniqueness.
    """
    date_part = timezone.localdate().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()

    return f"TKT-{date_part}-{random_part}"


@transaction.atomic
def create_customer_ticket(*, customer, title, description, category):
    """
    Create a ticket for an authenticated customer.
    """
    for attempt in range(3):
        ticket_number = generate_ticket_number()

        try:
            with transaction.atomic():
                return Ticket.objects.create(
                    ticket_number=ticket_number,
                    customer=customer,
                    created_by=customer,
                    created_source=Ticket.CreatedSource.CUSTOMER,
                    title=title,
                    description=description,
                    category=category,
                    priority=Ticket.Priority.MEDIUM,
                    status=Ticket.Status.OPEN,
                )
        except IntegrityError:
            if attempt == 2:
                raise

    raise RuntimeError("Unable to generate a unique ticket number.")


class TicketAssignmentError(Exception):
    """Raised when a ticket assignment operation is invalid."""


@transaction.atomic
def assign_ticket(*, ticket_id, agent_id, assigned_by, reason=""):
    """
    Assign or reassign a ticket to an eligible agent.

    Only an active administrator may initiate this operation.
    Previous assignments are retained as history.
    """
    if (
        not assigned_by.is_authenticated
        or not assigned_by.is_active
        or assigned_by.status != User.Status.ACTIVE
        or assigned_by.role != User.Role.ADMIN
    ):
        raise TicketAssignmentError(
            "Only active administrators may assign tickets."
        )

    try:
        ticket = Ticket.objects.select_for_update().get(
            id=ticket_id
        )
    except Ticket.DoesNotExist as exc:
        raise TicketAssignmentError(
            "The requested ticket does not exist."
        ) from exc

    try:
        agent = User.objects.get(
            id=agent_id,
            role=User.Role.AGENT,
            is_active=True,
            status=User.Status.ACTIVE,
        )
    except User.DoesNotExist as exc:
        raise TicketAssignmentError(
            "The selected account is not an eligible active agent."
        ) from exc

    current_assignment = (
        TicketAssignment.objects
        .select_for_update()
        .filter(
            ticket=ticket,
            unassigned_at__isnull=True,
        )
        .order_by("-assigned_at")
        .first()
    )

    if current_assignment and current_assignment.agent_id == agent.id:
        raise TicketAssignmentError(
            "This ticket is already assigned to the selected agent."
        )

    if current_assignment:
        current_assignment.unassigned_at = timezone.now()
        current_assignment.save(update_fields=["unassigned_at"])

    return TicketAssignment.objects.create(
        ticket=ticket,
        agent=agent,
        assigned_by=assigned_by,
        reason=reason,
    )

class TicketEscalationError(Exception):
    """Raised when a ticket escalation operation is invalid."""


@transaction.atomic
def escalate_ticket(
    *,
    ticket_id,
    escalated_by,
    reason,
    trigger,
    conversation=None,
):
    """
    Escalate an existing ticket and preserve escalation history.

    Only active administrators and agents may initiate manual
    escalations through this service. Automated escalation triggers
    may use escalated_by=None.

    The ticket status changes to ESCALATED unless it is already
    resolved or closed.
    """

    if escalated_by is not None:
        if (
            not escalated_by.is_authenticated
            or not escalated_by.is_active
            or escalated_by.status != User.Status.ACTIVE
            or escalated_by.role not in (
                User.Role.ADMIN,
                User.Role.AGENT,
            )
        ):
            raise TicketEscalationError(
                "Only active agents and administrators may escalate tickets."
            )

    if not isinstance(reason, str) or not reason.strip():
        raise TicketEscalationError(
            "An escalation reason is required."
        )

    valid_triggers = {
        choice[0]
        for choice in TicketEscalation.Trigger.choices
    }

    if trigger not in valid_triggers:
        raise TicketEscalationError(
            "The escalation trigger is invalid."
        )

    try:
        ticket = Ticket.objects.select_for_update().get(
            id=ticket_id
        )
    except Ticket.DoesNotExist as exc:
        raise TicketEscalationError(
            "The requested ticket does not exist."
        ) from exc

    if ticket.status in (
        Ticket.Status.RESOLVED,
        Ticket.Status.CLOSED,
    ):
        raise TicketEscalationError(
            "Resolved or closed tickets cannot be escalated."
        )

    if conversation is not None:
        if conversation.ticket_id != ticket.id:
            raise TicketEscalationError(
                "The conversation does not belong to this ticket."
            )

    escalation = TicketEscalation.objects.create(
        ticket=ticket,
        conversation=conversation,
        escalated_by=escalated_by,
        reason=reason.strip(),
        trigger=trigger,
    )

    if ticket.status != Ticket.Status.ESCALATED:
        ticket.status = Ticket.Status.ESCALATED
        ticket.save(update_fields=["status", "updated_at"])

    return escalation