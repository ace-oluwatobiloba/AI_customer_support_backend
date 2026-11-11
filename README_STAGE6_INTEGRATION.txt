STAGE 6 — CROSS-COMPONENT INTEGRATION TESTS
=============================================

Purpose
-------
Adds focused integration coverage for the existing support, audit, and
notification services. This stage does not introduce production features,
change models, or add migrations.

Files
-----
apps/support/test_modules/test_cross_component_integration.py

Coverage
--------
1. Successful automated ticket assignment:
   - assignment is persisted;
   - the system audit event references the correct ticket and agent;
   - the assigned agent receives an in-app notification;
   - the after-commit email callback completes and records SENT.

2. Email provider failure:
   - the assignment, audit event, and in-app notification remain persisted;
   - the email delivery is recorded as FAILED;
   - the external email provider is mocked.

3. Audit persistence failure:
   - the assignment and notification are rolled back with the business
     transaction;
   - the email callback is not executed;
   - no orphan audit record remains.

No external network calls are made by these tests. Resend is mocked.

Apply
-----
Extract this patch into the project root, preserving relative paths.
The patch contains one new test module and this README.

Verify
------
Run these commands from the project root with the project virtual
environment activated:

    python manage.py check
    python manage.py test apps.support.test_modules.test_cross_component_integration
    python manage.py test apps.audit apps.notifications apps.support apps.conversations apps.accounts
    python manage.py makemigrations --check --dry-run

The first targeted command isolates the new Stage 6 tests. The broader
regression command checks the previously implemented components together.
The final command confirms that no model changes or migrations were introduced.

Notes
-----
- Test counts can vary as the source evolves; use the actual test-run output.
- No existing source file is overwritten by this patch.
- No .env files, credentials, tokens, database files, virtual environments,
  Git metadata, or generated artifacts are included.
