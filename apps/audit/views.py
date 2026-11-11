"""Administrator-only, read-only audit-log API."""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.audit.pagination import AuditLogPagination
from apps.audit.serializers import AuditLogSerializer
from apps.support.permissions import IsAdmin


class AuditLogQuerysetMixin:
    """Build a bounded audit queryset with optional exact-match filters."""

    serializer_class = AuditLogSerializer
    permission_classes = (IsAuthenticated, IsAdmin)
    pagination_class = AuditLogPagination

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor").order_by(
            "-created_at", "-id"
        )

        action = self.request.query_params.get("action")
        entity_type = self.request.query_params.get("entity_type")
        actor_id = self.request.query_params.get("actor_id")

        if action:
            queryset = queryset.filter(action=action.strip())
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type.strip())
        if actor_id:
            queryset = queryset.filter(actor_id=actor_id.strip())

        return queryset


class AuditLogListView(AuditLogQuerysetMixin, generics.ListAPIView):
    """List audit records; accessible only to active administrators."""


class AuditLogDetailView(AuditLogQuerysetMixin, generics.RetrieveAPIView):
    """Retrieve one audit record; accessible only to active administrators."""

    lookup_field = "id"
    lookup_url_kwarg = "audit_log_id"
