"""Read-only Django Admin registration for audit history."""

from django.contrib import admin

from apps.accounts.admin import secure_admin_site
from apps.audit.models import AuditLog


@admin.register(AuditLog, site=secure_admin_site)
class AuditLogAdmin(admin.ModelAdmin):
    """Allow eligible administrators to inspect, but not alter, audit events."""

    list_display = (
        "created_at",
        "action",
        "entity_type",
        "entity_id",
        "actor",
        "ip_address",
    )
    list_filter = ("action", "entity_type", "created_at")
    search_fields = (
        "action",
        "entity_type",
        "actor__email",
        "user_agent",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("actor",)
    list_per_page = 50
    readonly_fields = (
        "id",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Disallow editing historical audit records, including via direct URLs.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(
            super().has_view_permission(request, obj)
            or (request.user.is_active and request.user.is_superuser)
        )
