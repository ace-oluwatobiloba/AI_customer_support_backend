STAGE 5 — AUDIT ADMINISTRATION AND ACCESS CONTROL
==================================================

Purpose
-------
Adds read-only audit inspection to the existing secure Django Admin site and
an administrator-only read API. The existing AuditLog model and centralized
record_audit_event service are preserved.

Files
-----
apps/audit/admin.py
    Registers AuditLog on the existing secure_admin_site. Audit records cannot
    be added, edited, or deleted through Django Admin.

apps/audit/serializers.py
    Read-only API representation of audit events.

apps/audit/pagination.py
    Page-number pagination, 50 records by default, maximum 100.

apps/audit/views.py
    Administrator-only list and detail views. Supports exact-match filters:
    action, entity_type, actor_id.

apps/audit/urls.py
    Routes for audit list and detail.

apps/audit/test_modules/test_audit_api.py
    Tests API access control, filtering, detail retrieval and admin read-only
    behaviour.

config/urls.py
    Mounts the audit API at /api/v1/audit/.

API
---
GET /api/v1/audit/
GET /api/v1/audit/<uuid>/

Optional list query parameters:
    action=<event action>
    entity_type=<entity type>
    actor_id=<actor UUID>
    page=<page number>
    page_size=<1..100>

Access
------
Both API endpoints require authentication and an active ADMIN role.
Customers and agents receive HTTP 403.
The API is read-only. No create, update, or delete endpoint is provided.

The Admin registration uses the existing secure_admin_site, which already
restricts Admin access to eligible administrator accounts. Audit records
cannot be added, changed, or deleted through this ModelAdmin.

Apply
-----
Extract this patch into the project root, preserving relative paths.

Verify
------
python manage.py check
python manage.py test apps.audit
python manage.py test apps.accounts
python manage.py makemigrations --check --dry-run

No model changes or migrations are included.
