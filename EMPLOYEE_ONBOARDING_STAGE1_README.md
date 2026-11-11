# Employee onboarding — implementation patch (Stage 1)

This patch adds administrator-controlled employee invitations and Agent account provisioning to
`apps.accounts`. It does not introduce a Business model or multi-tenant architecture.

## Files
- `apps/accounts/models.py`: adds `EmployeeInvitation`.
- `apps/accounts/migrations/0004_employeeinvitation.py`: database migration.
- `apps/accounts/services/employee_onboarding.py`: invitation and acceptance service.
- `apps/accounts/serializers/employee_onboarding.py`: API validation and response serializers.
- `apps/accounts/views.py`, `apps/accounts/urls.py`: invitation and agent-management endpoints.
- `apps/accounts/test_modules/test_employee_onboarding.py`: focused tests.

## Endpoints
- `POST /api/v1/auth/employees/invitations/` — administrator invites an employee.
- `GET /api/v1/auth/employees/invitations/` — administrator lists invitations.
- `POST /api/v1/auth/employees/invitations/accept/` — invitee accepts and creates Agent credentials.
- `GET /api/v1/auth/employees/agents/` — administrator lists agents.
- `PATCH /api/v1/auth/employees/agents/<uuid:user_id>/status/` — administrator activates,
  deactivates, or suspends an agent.

Invitation email contains a high-entropy, single-use token. Only its SHA-256 hash is stored.
Acceptance verifies the token, validates the password, creates an email-verified AGENT account,
creates its AgentProfile, marks the invitation accepted, and records audit events.

## Apply in the local project
1. Back up the active PostgreSQL database before applying schema changes.
2. Copy the included files into the matching paths in your project, preserving other code.
3. Run:
   `python manage.py migrate`
   `python manage.py check`
   `python manage.py test apps.accounts.test_modules.test_employee_onboarding`
   `python manage.py spectacular --file schema.yml --validate`
4. Inspect the migration plan first if your local migration history differs:
   `python manage.py showmigrations accounts audit`

Do not run this patch against a database until the backup is verified. Do not share `.env` or credentials.

## Scope boundary
This is Stage 1 only. It does not yet implement agent/admin conversation replies, agent ticket workspace
updates, or changes to ticket assignment/reassignment. Those are subsequent stages. The code was
syntax-compiled in the preparation environment, but Django tests and migration checks could not be
executed here because the project dependencies and PostgreSQL runtime were not available.
