"""Business rules for human-agent conversation handover."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record_audit_event
from apps.conversations.models import Conversation, Message
from apps.support.models import TicketAssignment


class ConversationHandoverError(Exception):
    """Raised when a human handover operation is not permitted."""


def _is_active_staff(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.status == User.Status.ACTIVE
        and user.role in (User.Role.AGENT, User.Role.ADMIN)
    )


def current_ticket_assignment(ticket):
    if ticket is None:
        return None
    return (
        TicketAssignment.objects
        .filter(ticket=ticket, unassigned_at__isnull=True)
        .select_related("agent")
        .order_by("-assigned_at")
        .first()
    )


def can_access_staff_conversation(user, conversation):
    """Agents need the current ticket assignment; admins can access all."""
    if not _is_active_staff(user):
        return False
    if user.role == User.Role.ADMIN:
        return True
    assignment = current_ticket_assignment(conversation.ticket)
    return bool(assignment and assignment.agent_id == user.id)


def staff_conversation_queryset(user):
    """Return only escalated/agent-active conversations visible to staff."""
    if not _is_active_staff(user):
        return Conversation.objects.none()

    queryset = Conversation.objects.filter(
        status__in=(
            Conversation.Status.ESCALATED,
            Conversation.Status.AGENT_ACTIVE,
        ),
        ticket__isnull=False,
    ).select_related("customer", "ticket")

    if user.role == User.Role.AGENT:
        queryset = queryset.filter(
            ticket__assignments__agent=user,
            ticket__assignments__unassigned_at__isnull=True,
        )

    return queryset.distinct().order_by("-updated_at")


@transaction.atomic
def take_over_conversation(*, conversation_id, actor):
    """Move an escalated conversation into human handling atomically."""
    if not _is_active_staff(actor):
        raise ConversationHandoverError(
            "Only active agents and administrators may take over conversations."
        )

    try:
        conversation = (
            Conversation.objects.select_for_update()
            .get(pk=conversation_id)
        )
    except Conversation.DoesNotExist as exc:
        raise ConversationHandoverError("Conversation not found.") from exc

    if conversation.status != Conversation.Status.ESCALATED:
        raise ConversationHandoverError(
            "Only escalated conversations can be taken over."
        )

    if conversation.ticket_id is None:
        raise ConversationHandoverError(
            "This conversation has no support ticket and cannot be taken over."
        )

    if actor.role == User.Role.AGENT and not can_access_staff_conversation(
        actor, conversation
    ):
        raise ConversationHandoverError(
            "This conversation is not assigned to you."
        )

    conversation.status = Conversation.Status.AGENT_ACTIVE
    conversation.save(update_fields=["status", "updated_at"])

    record_audit_event(
        actor=actor,
        action="CONVERSATION_TAKEN_OVER",
        entity=conversation,
        metadata={"ticket_id": str(conversation.ticket_id)},
    )
    return conversation


@transaction.atomic
def create_human_reply(*, conversation_id, actor, content):
    """Persist an authenticated human reply after validating access."""
    if not _is_active_staff(actor):
        raise ConversationHandoverError(
            "Only active agents and administrators may reply as support staff."
        )

    content = content.strip() if isinstance(content, str) else ""
    if not content:
        raise ConversationHandoverError("Message content cannot be blank.")
    if len(content) > 10000:
        raise ConversationHandoverError("Message content exceeds 10000 characters.")

    try:
        conversation = (
            Conversation.objects.select_for_update()
            .get(pk=conversation_id)
        )
    except Conversation.DoesNotExist as exc:
        raise ConversationHandoverError("Conversation not found.") from exc

    if conversation.status != Conversation.Status.AGENT_ACTIVE:
        raise ConversationHandoverError(
            "Take over the escalated conversation before replying."
        )

    if not can_access_staff_conversation(actor, conversation):
        raise ConversationHandoverError(
            "You are not authorized to reply to this conversation."
        )

    sender_type = (
        Message.SenderType.ADMIN
        if actor.role == User.Role.ADMIN
        else Message.SenderType.AGENT
    )
    message = Message.objects.create(
        conversation=conversation,
        sender_user=actor,
        sender_type=sender_type,
        content=content,
    )
    conversation.save(update_fields=["updated_at"])

    record_audit_event(
        actor=actor,
        action="CONVERSATION_HUMAN_REPLY",
        entity=conversation,
        metadata={"message_id": str(message.id), "sender_type": sender_type},
    )
    return message
