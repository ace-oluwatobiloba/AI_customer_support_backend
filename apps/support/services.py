"""
Business services for support ticket management.
"""

import secrets
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record_audit_event
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
                ticket = Ticket.objects.create(
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
                record_audit_event(
                    actor=customer,
                    action="TICKET_CREATED",
                    entity=ticket,
                    metadata={
                        "ticket_number": ticket.ticket_number,
                        "created_source": ticket.created_source,
                        "category": ticket.category,
                    },
                )
                return ticket
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

    assignment = TicketAssignment.objects.create(
        ticket=ticket,
        agent=agent,
        assigned_by=assigned_by,
        reason=reason,
    )
    record_audit_event(
        actor=assigned_by,
        action="TICKET_ASSIGNED",
        entity=ticket,
        metadata={
            "assignment_id": str(assignment.pk),
            "agent_id": str(agent.pk),
            "previous_agent_id": (
                str(current_assignment.agent_id)
                if current_assignment else None
            ),
        },
    )
    return assignment

@transaction.atomic
def auto_assign_ticket(*, ticket_id):
    """
    Assign an unassigned ticket to the least-loaded eligible agent.

    Returns the new TicketAssignment, or None if no eligible agent
    has capacity. Automated assignments have no human assigner.
    """
    try:
        ticket = Ticket.objects.select_for_update().get(id=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise TicketAssignmentError(
            "The requested ticket does not exist."
        ) from exc

    if ticket.status in (
        Ticket.Status.RESOLVED,
        Ticket.Status.CLOSED,
    ):
        raise TicketAssignmentError(
            "Resolved or closed tickets cannot be auto-assigned."
        )

    current_assignment = (
        TicketAssignment.objects.select_for_update()
        .filter(
            ticket=ticket,
            unassigned_at__isnull=True,
        )
        .order_by("-assigned_at")
        .first()
    )

    # Do not silently replace an existing human assignment.
    if current_assignment is not None:
        return current_assignment

    max_workload = getattr(
        settings,
        "SUPPORT_AGENT_MAX_ACTIVE_TICKETS",
        5,
    )

    if max_workload < 1:
        return None

    eligible_agents = User.objects.filter(
        role=User.Role.AGENT,
        is_active=True,
        status=User.Status.ACTIVE,
    )

    # Lock eligible agent rows in a consistent order so concurrent
    # automated assignments do not freely select the same workload.
    list(
        eligible_agents.select_for_update()
        .order_by("id")
        .values_list("id", flat=True)
    )

    active_ticket_statuses = [
        Ticket.Status.OPEN,
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.WAITING_FOR_CUSTOMER,
        Ticket.Status.ESCALATED,
    ]

    agent = (
        eligible_agents.annotate(
            active_workload=Count(
                "ticket_assignments",
                distinct=True,
                filter=Q(
                    ticket_assignments__unassigned_at__isnull=True,
                    ticket_assignments__ticket__status__in=(
                        active_ticket_statuses
                    ),
                ),
            ),
            last_assigned_at=Max(
                "ticket_assignments__assigned_at",
            ),
        )
        .filter(active_workload__lt=max_workload)
        .order_by(
            "active_workload",
            F("last_assigned_at").asc(nulls_first=True),
            "id",
        )
        .first()
    )

    if agent is None:
        return None

    assignment = TicketAssignment.objects.create(
        ticket=ticket,
        agent=agent,
        assigned_by=None,
        reason=(
            "Automated assignment: least-loaded eligible agent "
            "with available capacity."
        ),
    )

    # Persist the in-app notification in this transaction. The centralized
    # service schedules email only after commit; delivery failure cannot undo
    # the assignment or remove the in-app notification.
    from apps.notifications.models import Notification
    from apps.notifications.services.notification_service import create_notification

    create_notification(
        user=agent,
        notification_type=Notification.Type.TICKET_ASSIGNED,
        title="New support ticket assigned",
        message=(
            f"Ticket {ticket.ticket_number} - {ticket.title} "
            "has been assigned to you."
        ),
        send_email=True,
    )

    record_audit_event(
        actor=None,
        action="TICKET_AUTO_ASSIGNED",
        entity=ticket,
        metadata={
            "assignment_id": str(assignment.pk),
            "agent_id": str(agent.pk),
            "assignment_method": "LEAST_LOADED",
        },
    )
    return assignment


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

    record_audit_event(
        actor=escalated_by,
        action="TICKET_ESCALATED",
        entity=ticket,
        metadata={
            "escalation_id": str(escalation.pk),
            "trigger": trigger,
            "conversation_id": (
                str(conversation.pk) if conversation is not None else None
            ),
        },
    )
    return escalation