# Staff Portal and API Documentation Access

## What this patch changes

- Adds a session-authenticated staff sign-in page at `/staff/login/`.
- Adds a staff portal at `/staff/`.
- Shows Swagger UI, ReDoc and the OpenAPI schema links to active agents and administrators.
- Shows the Django administration link only to administrators.
- Restricts all three documentation endpoints to active agents and administrators.
- Uses Django `SessionAuthentication` for the browser documentation endpoints so a staff login session is recognized. The API's JWT authentication defaults remain unchanged.
- Does not add or change database models; no migration is required.

## Apply

Extract the patch archive into the project root, preserving folder paths and allowing the files to overwrite the listed existing files.

## Access

- Staff sign-in: `/staff/login/`
- Staff portal: `/staff/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

Staff must sign in using their account email and password. Only users with role `AGENT` or `ADMIN`, status `ACTIVE`, and `is_active=True` can enter the staff portal or view documentation. Customers and anonymous visitors are denied.

The Django administration link is displayed only to administrators. The existing admin site's own authorization remains in force.

## Validation

Run:

```powershell
python -m compileall config
python manage.py check
python manage.py makemigrations --check --dry-run
```

Then manually verify:
1. Anonymous visit to `/staff/` redirects to `/staff/login/`.
2. Active agent can sign in and access all three documentation pages.
3. Active administrator can sign in and access all three documentation pages and sees the administration link.
4. Customer, inactive or suspended staff accounts cannot access the staff portal or documentation.
5. Anonymous requests to `/api/docs/`, `/api/redoc/` and `/api/schema/` are denied.

The OpenAPI schema may still describe endpoints that have their own role-based authorization. Documentation access does not grant permission to call those endpoints.
