# Backblaze B2 + clean-slate patch

This patch is based on the uploaded `ai_customer_support-current-source.zip`. It configures Django's existing `django-storages` S3 backend for Backblaze B2 and adds an explicitly gated cleanup command.

## Important scope

The cleanup command removes **all** KnowledgeDocument, KnowledgeDocumentVersion, and DocumentChunk rows; all Ticket, TicketAssignment, and TicketEscalation rows; and conversations that have a non-null ticket link, including their messages and revisions. It preserves users, profiles, employee invitations, standalone conversations, and unrelated records. Review the dry-run counts before executing.

The cleanup checks both the legacy local `MEDIA_ROOT` and the active configured storage backend for document objects. If the previous source was an AWS bucket, the command cannot remove those old AWS objects after AWS settings are removed; verify the old bucket is empty or remove the single test object separately before revoking AWS credentials. The inspected support and conversation models contain no FileField/ImageField attachment model. If ticket attachments are stored in another app or external service not represented in these models, they are not handled by this command.

AuditLog rows are deliberately preserved as accountability history.

## 1. Back up PostgreSQL first

Use your existing database backup procedure. For a local PostgreSQL installation, for example:

```powershell
pg_dump -Fc -h localhost -p 5432 -U YOUR_DB_USER -d YOUR_DB_NAME -f .\backups\before_b2_clean_slate.dump
```

Create the `backups` directory first if needed. Do not place the dump in the patch ZIP.

## 2. Apply patch

Extract this ZIP into the project root, preserving paths. Review `.env.example` and add the B2 variables to your actual `.env` (do not overwrite `.env`). Set `USE_B2_STORAGE=true`. Do not paste credentials into source files or Git.

The bucket must be private. Use the bucket-restricted B2 application key with read/write permissions.

## 3. Check before cleanup

```powershell
python manage.py check
python manage.py migrate --check
python manage.py clean_test_data
```

The last command is a dry run and only prints counts. Verify the counts and confirm the database is the intended development/test database.

## 4. Execute cleanup

```powershell
python manage.py clean_test_data --confirm
```

This is destructive and cannot be undone without restoring the backup. It deletes all knowledge-base records and all tickets, not only records with a particular title/status. It also deletes conversations linked to tickets because the current schema uses PROTECT relationships. Standalone conversations are retained.

Run this only after reviewing the dry-run output and confirming the backup exists.

## 5. Validate B2

After dependencies are already installed (boto3 and django-storages are pinned in the inspected requirements), run Django checks and your knowledge tests. Then upload a fresh test PDF/DOCX/TXT through the existing API and verify object creation, document processing, pgvector chunks, retrieval, and deletion.

## Configuration notes

- B2 endpoint: `https://s3.eu-central-003.backblazeb2.com`
- Region: `eu-central-003`
- Signature: `s3v4`
- Private objects; query-string-authenticated URLs expire after 900 seconds.
- Encryption remains configured at the bucket level in the Backblaze console; the Django client does not override it per object.
- AWS storage settings are removed from Django's active storage configuration. Do not revoke/delete AWS credentials or buckets until confirming no other application component uses them and the new B2 upload/ingestion/retrieval/delete lifecycle passes.

## Limitations

This patch has been statically generated from the provided source archive. It has not been run against your actual `.env`, PostgreSQL database, Podman containers, or Backblaze account. No database records are deleted by extracting this ZIP; cleanup occurs only when you explicitly run the management command with `--confirm`.
