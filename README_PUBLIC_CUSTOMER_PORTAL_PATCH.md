# Public Customer Portal patch

## Changes
- Replaces the public homepage with an organization-branded customer portal.
- Adds configurable branding settings: ORGANIZATION_NAME, ORGANIZATION_TAGLINE,
  ORGANIZATION_SUPPORT_EMAIL, ORGANIZATION_SUPPORT_PHONE.
- Adds the project-level `templates/` directory to Django template discovery.
- Routes all customer-facing support actions to the existing `/chat/` page.
- Restricts OpenAPI schema, Swagger UI and ReDoc to authenticated, active ADMIN users.
- Does not change models, migrations, existing APIs, Celery tasks or Redis settings.

## Apply
Extract this patch into the project root, allowing files to overwrite their matching
versions. Review the diff before committing.

Add optional public branding values to `.env`:
```dotenv
ORGANIZATION_NAME="Your Organization"
ORGANIZATION_TAGLINE="Helpful answers. Human support. A better experience."
ORGANIZATION_SUPPORT_EMAIL="support@example.com"
ORGANIZATION_SUPPORT_PHONE="+234..."
```
These are optional; defaults are provided.

## Validate
```powershell
python -m compileall config apps
python manage.py check
python manage.py test
```

## Access expectations
- `/` is public.
- `/chat/` is publicly reachable, but the existing chat interface requires customer
  authentication before accessing conversations.
- `/api/schema/`, `/api/docs/`, and `/api/redoc/` require an authenticated,
  active administrator account.
- `/admin/` retains the existing secure admin-site configuration.

This patch intentionally does not add a separate customer registration HTML form.
Customer registration remains available through the existing API endpoint until
we implement a dedicated registration page as a separate UI change.
