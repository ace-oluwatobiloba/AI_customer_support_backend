# Agent handover patch

Apply this patch from the Django project root (`C:\\Users\\HP\\ai_customer_support`).

## Files included
- `apps/conversations/models.py` — adds `ADMIN` as a message sender type.
- `apps/conversations/urls.py` — registers staff inbox and takeover routes.
- `apps/conversations/views.py` — adds staff inbox/takeover and routes staff message POSTs through the human-reply service; customer AI flow remains in place.
- `apps/conversations/services/handover_service.py` — authorization, atomic takeover, human replies, audit logging.
- `apps/conversations/services/escalation_service.py` — attempts least-loaded ticket assignment after customer escalation, without replacing an existing assignment.

## Apply
1. Back up the five existing files.
2. Extract this ZIP into the project root and allow the five files to be replaced.
3. Run:
   ```powershell
   python -m compileall apps/conversations
   python manage.py check
   python manage.py makemigrations --check --dry-run
   python manage.py test apps.conversations
   python manage.py test apps.support
   ```
4. Do not run migrations unless `makemigrations --check --dry-run` reports a real model change. The `ADMIN` sender choice is a model choice addition and normally does not require a database migration.

## New routes
- `GET /api/v1/conversations/agent/` — active agent sees currently assigned escalated/agent-active conversations; admin sees all such conversations.
- `POST /api/v1/conversations/<conversation_id>/takeover/` — assigned agent or admin moves an escalated conversation to `AGENT_ACTIVE`.
- Existing `GET/POST /api/v1/conversations/<conversation_id>/messages/` — customer behavior remains; active assigned agents and admins can GET history and POST human replies after takeover.

## Important behavior
- TicketAssignment is the source of truth for agent access.
- Agent access requires a current assignment (`unassigned_at IS NULL`).
- Agents cannot take over another agent's ticket.
- Admins can access and take over any ticket-linked conversation.
- Human replies are stored as `AGENT` or `ADMIN` message sender types and are not sent to the RAG pipeline.
- Audit records are written for takeover and human replies.
- Customer-requested escalation attempts least-loaded assignment. If no eligible agent has capacity, the ticket remains escalated and unassigned for admin action.

## Verification limitation
This patch was generated against the supplied source archive, not executed inside your local Django environment. Run the checks above and share the first traceback if any command fails. Do not proceed to live browser testing until the test suite passes.
