# Celery + Redis integration — Stage 1

## Included
- Django Celery bootstrap and configuration snippet.
- Redis broker/result backend and Podman Compose services.
- Async knowledge ingestion after database commit.
- Async Resend notification email delivery with bounded retries.
- Celery Beat invitation expiry every 15 minutes.
- AI-triggered ticket assignment retry using the existing least-loaded assignment service.

## Apply
Extract this ZIP into the project root, preserving relative paths. The archive already contains the updated `config/settings.py`; no manual
settings edits are required. Dependencies are already present in requirements.txt.

Add to local `.env`: `REDIS_URL=redis://127.0.0.1:6379/0`. Inside compose,
services use `redis://redis:6379/0`.

## Local Windows worker
Start a local Redis server, then run in separate PowerShell terminals:
```powershell
celery -A config worker --loglevel=INFO --pool=solo
celery -A config beat --loglevel=INFO
```

## Podman
Ensure `.env` includes all existing variables, including DB_NAME, DB_USER,
CONTAINER_DB_PASSWORD, Django, AI and Resend settings. Then:
```powershell
podman compose config
podman compose up --build -d
podman compose ps
podman compose logs -f web celery-worker celery-beat redis
```

PostgreSQL's existing host port 5433 and data volume are preserved. The web
and worker containers share `media_data`, so uploaded documents are available
to workers.

## Behaviour and limitations
- No database schema changes.
- Ticket assignment is queued after escalation commits. Existing assignments
  are preserved; no eligible agent/capacity and transient DB errors retry with
  bounded exponential delays (up to five retries). Invalid/closed tickets do
  not retry.
- Notification delivery retries provider failures up to three times. This
  cannot bypass Resend account restrictions.
- If Redis is down at enqueue time, the saved business record remains; the
  task is logged but requires operational re-queue.
- Invitation expiry runs every 15 minutes.

## Validate after applying
```powershell
python -m compileall config apps
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.knowledge apps.notifications apps.support apps.conversations apps.accounts
```
