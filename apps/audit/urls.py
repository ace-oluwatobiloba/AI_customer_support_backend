"""URL routes for administrator audit-log inspection."""

from django.urls import path

from apps.audit.views import AuditLogDetailView, AuditLogListView

app_name = "audit"

urlpatterns = [
    path("", AuditLogListView.as_view(), name="audit-log-list"),
    path(
        "<uuid:audit_log_id>/",
        AuditLogDetailView.as_view(),
        name="audit-log-detail",
    ),
]
