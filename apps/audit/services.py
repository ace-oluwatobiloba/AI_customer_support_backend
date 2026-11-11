"""Centralized audit-event recording services.

Business services should use ``record_audit_event`` instead of creating
``AuditLog`` rows directly. Call it inside the caller's ``transaction.atomic``
block when the audit record must commit or roll back with the business change.
"""

from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from apps.audit.models import AuditLog


def _resolve_actor(actor):
    """Return an authenticated actor, or None for anonymous/system events."""
    if actor is None or isinstance(actor, AnonymousUser):
        return None
    if not getattr(actor, "is_authenticated", False):
        raise ValidationError("Audit actor must be an authenticated user or None.")
    return actor


def _resolve_entity(entity=None, *, entity_type=None, entity_id=None):
    """Resolve an entity instance or explicit entity type/UUID pair."""
    if entity is not None:
        if entity_type is not None or entity_id is not None:
            raise ValidationError(
                "Pass either entity or entity_type/entity_id, not both."
            )
        entity_type = entity.__class__.__name__
        entity_id = getattr(entity, "pk", None)

    if not isinstance(entity_type, str) or not entity_type.strip():
        raise ValidationError("A non-empty entity_type is required.")

    if entity_id in (None, ""):
        resolved_id = None
    else:
        try:
            resolved_id = UUID(str(entity_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError("entity_id must be a valid UUID.") from exc

    return entity_type.strip(), resolved_id


def _request_metadata(request):
    """Extract conservative request metadata without trusting forwarded IPs."""
    if request is None:
        return None, None

    meta = getattr(request, "META", {}) or {}
    ip_address = meta.get("REMOTE_ADDR") or None
    user_agent = meta.get("HTTP_USER_AGENT") or None

    # GenericIPAddressField validates the address on persistence; reject bad
    # request metadata early rather than making an otherwise valid event fail.
    if ip_address:
        from django.core.validators import validate_ipv46_address

        try:
            validate_ipv46_address(ip_address)
        except ValidationError:
            ip_address = None

    return ip_address, user_agent


def record_audit_event(
    *,
    action,
    actor=None,
    entity=None,
    entity_type=None,
    entity_id=None,
    metadata=None,
    request=None,
):
    """Persist one audit event and return its ``AuditLog`` instance.

    ``entity`` may be a Django model instance. For events without a concrete
    model instance, provide ``entity_type`` and optionally ``entity_id``.
    ``metadata`` must be a dictionary (or None) so event payloads remain
    structured and predictable.

    This function intentionally does not open its own transaction. The caller
    controls transaction boundaries so audit records can participate in the
    same transaction as the business operation.
    """
    if not isinstance(action, str) or not action.strip():
        raise ValidationError("A non-empty action is required.")
    action = action.strip()
    if len(action) > 100:
        raise ValidationError("action must be 100 characters or fewer.")

    resolved_actor = _resolve_actor(actor)
    resolved_entity_type, resolved_entity_id = _resolve_entity(
        entity, entity_type=entity_type, entity_id=entity_id
    )

    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError("metadata must be a dictionary or None.")

    ip_address, user_agent = _request_metadata(request)

    return AuditLog.objects.create(
        actor=resolved_actor,
        action=action,
        entity_type=resolved_entity_type,
        entity_id=resolved_entity_id,
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )
