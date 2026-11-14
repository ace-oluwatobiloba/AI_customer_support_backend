\# AI Customer Support Backend



A Django REST Framework backend for AI-assisted customer support, ticket management, knowledge-base retrieval, and human-agent escalation.



The system combines customer-facing support interfaces with authenticated APIs, role-based staff access, asynchronous background processing, and PostgreSQL-backed data management.



\## 1. Project Overview



The AI Customer Support Backend provides a centralized platform for organizations to manage customer support operations.



\### Core capabilities



\- Customer registration, authentication, and account verification.

\- Role-based access control for Customers, Agents, and Administrators.

\- Customer support conversations and messaging.

\- AI-assisted responses using a knowledge-base retrieval workflow.

\- Knowledge-base document upload and processing.

\- Document extraction, text chunking, embedding generation, and vector retrieval.

\- Support ticket creation, assignment, escalation, and lifecycle management.

\- Agent workload-aware ticket assignment.

\- Human-agent takeover of AI-assisted conversations.

\- In-app notifications and email delivery through Resend.

\- Audit logging for important system operations.

\- Background task execution using Celery and Redis.

\- Scheduled employee invitation expiry.

\- Interactive API documentation through Swagger UI and ReDoc.



\## 2. Technology Stack



| Component | Technology |

|---|---|

| Backend framework | Django 6.1 |

| API framework | Django REST Framework |

| Authentication | JWT and Django sessions |

| API documentation | drf-spectacular / OpenAPI |

| Database | PostgreSQL |

| Vector database extension | pgvector |

| ORM | Django ORM |

| Background processing | Celery |

| Message broker | Redis |

| Email delivery | Resend HTTP API |

| Document extraction | pypdf and python-docx |

| AI integration in current knowledge services | Google Gemini SDK |

| Application server | Gunicorn |

| Containerization | Podman / Compose |

| Language | Python 3.14 |



\## 3. System Architecture



The application follows a modular Django architecture.



```text

&#x20;                   CUSTOMERS

&#x20;                       |

&#x20;               Public Customer Portal

&#x20;                       |

&#x20;                 Customer Chat

&#x20;                       |

&#x20;                 Django Backend

&#x20;                       |

&#x20;       +---------------+----------------+

&#x20;       |               |                |

&#x20;   Accounts         Support        Conversations

&#x20;       |               |                |

&#x20;       +---------------+----------------+

&#x20;                       |

&#x20;              Knowledge Services

&#x20;                       |

&#x20;            Retrieval-Augmented

&#x20;              Generation (RAG)

&#x20;                       |

&#x20;         +-------------+-------------+

&#x20;         |                           |

&#x20;     PostgreSQL                  AI Provider

&#x20;     + pgvector                  Gemini

&#x20;         |

&#x20;   Document Chunks

&#x20;   and Embeddings





&#x20;              BACKGROUND PROCESSING

&#x20;                       |

&#x20;                     Celery

&#x20;                       |

&#x20;                     Redis

&#x20;                       |

&#x20;       +---------------+----------------+

&#x20;       |               |                |

&#x20; Notifications    Knowledge Tasks   Support Tasks

&#x20;       |               |                |

&#x20;     Resend          Document       Assignment

&#x20;                     Ingestion       Retries

&#x20;                       |

&#x20;                  Celery Beat

&#x20;                       |

&#x20;            Scheduled Invitation Expiry

```



\### Django applications



| Application | Responsibility |

|---|---|

| `accounts` | User accounts, authentication, customer and agent profiles, employee invitations |

| `support` | Tickets, assignments, escalations, and ticket workflows |

| `conversations` | Customer conversations, messages, and human handover |

| `knowledge` | Document management, extraction, chunking, embeddings, and RAG |

| `notifications` | In-app notifications and email delivery |

| `audit` | Audit records and administrative audit operations |

| `config` | Django project configuration, URLs, Celery bootstrap, permissions, and portal views |



\## 4. Repository Structure



```text

AI\_customer\_support\_backend/

│

├── apps/

│   ├── accounts/

│   ├── audit/

│   ├── conversations/

│   ├── knowledge/

│   ├── notifications/

│   └── support/

│

├── config/

│   ├── settings.py

│   ├── urls.py

│   ├── asgi.py

│   ├── wsgi.py

│   ├── celery.py

│   ├── home\_views.py

│   ├── staff\_views.py

│   └── permissions.py

│

├── templates/

│   ├── home.html

│   ├── staff\_login.html

│   └── staff\_portal.html

│

├── Containerfile

├── compose.yaml

├── manage.py

├── requirements.txt

├── .dockerignore

├── .gitignore

└── README.md

```



Each Django application contains its own models, migrations, serializers, views, services, URLs, and tests where applicable.



\## 5. Prerequisites



For local development:



\- Python 3.14

\- PostgreSQL with the pgvector extension installed

\- Redis

\- Git

\- A Resend account for transactional email functionality

\- An AI provider API key for knowledge-base answer generation and embeddings



For containerized deployment:



\- Podman

\- Podman Compose support

\- A working Podman machine on Windows



\## 6. Installation and Local Development



\### Step 1: Clone the repository



```powershell

git clone https://github.com/ace-oluwatobiloba/AI\_customer\_support\_backend.git



cd AI\_customer\_support\_backend

```



Switch to the development branch:



```powershell

git checkout feature/ticket-assignment

```



\### Step 2: Create a virtual environment



```powershell

python -m venv .venv

```



Activate it:



```powershell

.\\.venv\\Scripts\\Activate.ps1

```



Upgrade pip:



```powershell

python -m pip install --upgrade pip

```



Install dependencies:



```powershell

pip install -r requirements.txt

```



\### Step 3: Configure environment variables



Create a local `.env` file in the project root.



```powershell

Copy-Item .env.example .env

```



If `.env.example` has not yet been created, create `.env` manually using the configuration reference below.



\### Step 4: Prepare PostgreSQL



Create the application database and user using PostgreSQL.



Ensure the `vector` extension is available and enabled in the target database:



```sql

CREATE EXTENSION IF NOT EXISTS vector;

```



The application uses PostgreSQL with pgvector for vector-based knowledge retrieval.



\### Step 5: Run database migrations



```powershell

python manage.py migrate

```



\### Step 6: Create an administrator



```powershell

python manage.py createsuperuser

```



\### Step 7: Run the Django development server



```powershell

python manage.py runserver

```



The application will be available at:



`http://127.0.0.1:8000/`



\## 7. Environment Variables



The application loads local configuration from `.env`. Never commit actual credentials, API keys, or production secrets.



| Variable | Purpose |

|---|---|

| `DJANGO\_SECRET\_KEY` | Django cryptographic secret |

| `DJANGO\_DEBUG` | Enables or disables debug mode |

| `DJANGO\_ALLOWED\_HOSTS` | Comma-separated permitted hostnames |

| `DB\_NAME` | PostgreSQL database name |

| `DB\_USER` | PostgreSQL application user |

| `DB\_PASSWORD` | PostgreSQL application password |

| `DB\_HOST` | PostgreSQL hostname |

| `DB\_PORT` | PostgreSQL port |

| `CONTAINER\_DB\_PASSWORD` | Password used to initialize PostgreSQL in Compose |

| `REDIS\_URL` | Celery broker URL |

| `CELERY\_RESULT\_BACKEND` | Optional Celery result backend |

| `GEMINI\_API\_KEY` | Current knowledge-service AI provider key |

| `RESEND\_API\_KEY` | Resend API authentication |

| `RESEND\_API\_URL` | Resend email endpoint |

| `RESEND\_TIMEOUT` | Email request timeout |

| `DEFAULT\_FROM\_EMAIL` | Sender email address |

| `PUBLIC\_API\_BASE\_URL` | Public application base URL |

| `ORGANIZATION\_NAME` | Customer portal organization name |

| `ORGANIZATION\_TAGLINE` | Customer portal tagline |

| `ORGANIZATION\_SUPPORT\_EMAIL` | Public support email |

| `ORGANIZATION\_SUPPORT\_PHONE` | Public support phone |



For container deployment, `CONTAINER\_DB\_PASSWORD` must match the password configured as `DB\_PASSWORD` for Django to connect successfully.



\### Example local `.env`



```dotenv

DJANGO\_SECRET\_KEY=replace-with-a-long-random-secret

DJANGO\_DEBUG=True

DJANGO\_ALLOWED\_HOSTS=localhost,127.0.0.1



DB\_NAME=ai\_customer\_support

DB\_USER=ai\_support\_user

DB\_PASSWORD=replace-with-database-password

DB\_HOST=localhost

DB\_PORT=5432



CONTAINER\_DB\_PASSWORD=replace-with-the-same-database-password



REDIS\_URL=redis://127.0.0.1:6379/0



GEMINI\_API\_KEY=replace-with-ai-provider-key



RESEND\_API\_KEY=replace-with-resend-api-key

RESEND\_API\_URL=https://api.resend.com/emails

RESEND\_TIMEOUT=15

DEFAULT\_FROM\_EMAIL=onboarding@resend.dev



PUBLIC\_API\_BASE\_URL=http://127.0.0.1:8000



ORGANIZATION\_NAME=Your Organization

ORGANIZATION\_TAGLINE=Helpful answers. Human support. A better experience.

ORGANIZATION\_SUPPORT\_EMAIL=support@example.com

ORGANIZATION\_SUPPORT\_PHONE=+2340000000000

```



This is a configuration example, not a production-ready secrets file. Replace all placeholder values.



\## 8. Background Processing



Celery handles operations that should execute asynchronously instead of blocking the HTTP request cycle.



Redis acts as the message broker.



Current background task areas include:



\- Knowledge document ingestion.

\- Notification email delivery.

\- Automatic ticket assignment retries.

\- Employee invitation expiry.



Celery Beat schedules employee invitation expiry every 15 minutes.



\### Running Celery locally



Start Redis first.



Open a separate PowerShell terminal and run:



```powershell

celery -A config worker --loglevel=INFO --pool=solo

```



Start Celery Beat in another terminal:



```powershell

celery -A config beat --loglevel=INFO

```



The `--pool=solo` option is used for the local Windows worker.



\## 9. API Documentation and Access



The project provides three distinct user-facing access areas.



\### Public customer interface



| Route | Purpose |

|---|---|

| `/` | Public organization homepage |

| `/chat/` | Customer support chat interface |



The chat interface uses the existing customer authentication and conversation workflows.



\### Staff portal



| Route | Purpose |

|---|---|

| `/staff/login/` | Staff sign-in |

| `/staff/` | Staff portal |



Active Agents and Administrators can access the staff portal.



\### API documentation



| Route | Purpose |

|---|---|

| `/api/schema/` | OpenAPI schema |

| `/api/docs/` | Swagger UI |

| `/api/redoc/` | ReDoc documentation |



API documentation access is restricted to authenticated, active administrators and agents according to the implemented permissions.



The Django administration interface is available at:



`/admin/`



It retains its own Django admin authorization controls.



\### API endpoint groups



| Endpoint prefix | Application |

|---|---|

| `/api/v1/auth/` | Authentication and accounts |

| `/api/v1/knowledge/` | Knowledge-base management |

| `/api/v1/notifications/` | Notifications |

| `/api/v1/audit/` | Audit operations |

| `/api/v1/support/` | Ticket management |

| `/api/v1/conversations/` | Conversations and messaging |



JWT authentication is the default API authentication mechanism. Browser-based staff documentation access uses Django session authentication.



\## 10. Containerization with Podman



The project includes a `Containerfile` and `compose.yaml` for running the application and its supporting services together.



\### Services



| Service | Purpose |

|---|---|

| `db` | PostgreSQL with pgvector |

| `redis` | Celery message broker |

| `web` | Django application served through Gunicorn |

| `celery-worker` | Executes background tasks |

| `celery-beat` | Runs scheduled tasks |



\### Persistent volumes



| Volume | Purpose |

|---|---|

| `postgres\_data` | PostgreSQL database persistence |

| `redis\_data` | Redis persistence |

| `media\_data` | Uploaded document storage |

| `static\_data` | Collected static files |



The web and Celery worker services share the media volume so background tasks can access uploaded documents.



\### Container ports



| Service | Host port | Container port |

|---|---:|---:|

| Django web | 8000 | 8000 |

| PostgreSQL | 5433 | 5432 |



The web and PostgreSQL ports are bound to localhost in the current Compose configuration.



\### Validate Compose configuration



```powershell

podman compose config

```



\### Build and start all services



```powershell

podman compose up --build -d

```



\### Inspect running services



```powershell

podman compose ps

```



\### Apply database migrations



```powershell

podman compose exec web python manage.py migrate

```



\### Create an administrator



```powershell

podman compose exec web python manage.py createsuperuser

```



\### View service logs



```powershell

podman compose logs -f web celery-worker celery-beat redis

```



\### Stop services



```powershell

podman compose down

```



To stop services without deleting persistent data, do not add `-v`.



\*\*Warning:\*\* `podman compose down -v` removes named volumes and can delete persistent database and application data. Use it only when you intentionally want to remove that data.



\## 11. Testing



The project contains automated tests across its Django applications.



Run the complete test suite:



```powershell

python manage.py test --verbosity 2

```



Run tests for an individual application:



```powershell

python manage.py test apps.accounts

python manage.py test apps.support

python manage.py test apps.conversations

python manage.py test apps.knowledge

python manage.py test apps.notifications

python manage.py test apps.audit

```



Run Django system checks:



```powershell

python manage.py check

```



Check whether model changes require new migrations:



```powershell

python manage.py makemigrations --check --dry-run

```



\## 12. Security Considerations



\- Keep `.env` out of version control.

\- Never commit API keys, passwords, access tokens, or database backups.

\- Use a strong, unique `DJANGO\_SECRET\_KEY`.

\- Set `DJANGO\_DEBUG=False` in production.

\- Configure `DJANGO\_ALLOWED\_HOSTS` for the actual deployment domains.

\- Use HTTPS in production.

\- Keep database and Redis services private.

\- Apply least-privilege access to customer, agent, and administrator accounts.

\- Protect uploaded documents and knowledge-base resources.

\- Review application logs and audit records regularly.

\- Configure production email sender domains and provider credentials.



The repository's `.gitignore` excludes local environment files, Python environments, generated files, logs, database backups, and other development artifacts.



\## 13. Current Development Notes



\- The application uses PostgreSQL and pgvector; SQLite is not the intended application database.

\- The current knowledge-service answer generation and embedding implementations use the Google Gemini SDK.

\- The `openai` package is present in the dependency list, but an active OpenAI implementation should be verified before describing it as the current provider.

\- Email delivery uses the Resend HTTP API.

\- Celery tasks require a reachable Redis broker.

\- If Redis is unavailable when a task is enqueued, the business operation can persist while the task remains unqueued; operational re-queue handling is required.

\- Some integration tests currently have two deferred failures related to asynchronous notification delivery and the unavailable local Redis broker. These should be revisited when the dependent components and test environment are completed.



\## 14. Repository



\*\*GitHub:\*\* https://github.com/ace-oluwatobiloba/AI\_customer\_support\_backend



\*\*Current development branch:\*\* `feature/ticket-assignment`



To contribute:



1\. Fork or clone the repository.

2\. Create a feature branch.

3\. Implement and test your changes.

4\. Commit your changes with a descriptive message.

5\. Push your branch and open a pull request.



\---



\*AI Customer Support Backend — Modular support operations, knowledge retrieval, and human-agent workflows.\*

