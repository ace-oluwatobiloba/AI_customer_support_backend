# Backblaze B2 storage integration patch

## What this patch changes

- Adds a dedicated `USE_B2_STORAGE` setting and S3-compatible Backblaze B2 configuration in `config/settings.py`.
- Keeps the existing local filesystem mode as the default.
- Retains the previous AWS S3 configuration as a separate rollback option (`USE_S3_STORAGE`).
- Adds a management command to test upload, read-back, existence and deletion through Django's configured storage backend.
- Adds placeholder B2 variables to `.env.example`.

The knowledge-base upload and ingestion services already use Django's `default_storage` abstraction in the inspected source. They do not need provider-specific code changes. The `storage_key` remains the key stored in PostgreSQL; the original document bytes are stored in the configured object store.

## Backblaze configuration

In the project's root `.env`, set:

```dotenv
USE_B2_STORAGE=true
B2_BUCKET_NAME=ai-customer-support-kb-prod
B2_ENDPOINT_URL=https://s3.eu-central-003.backblazeb2.com
B2_REGION=eu-central-003
B2_KEY_ID=YOUR_BACKBLAZE_APPLICATION_KEY_ID
B2_APPLICATION_KEY=YOUR_BACKBLAZE_APPLICATION_KEY
```

Use the bucket-restricted application key created for this application. Do not use the Backblaze master application key. Do not paste credentials into chat or commit `.env` to Git. The key needs permission to upload, download and delete objects in this bucket. Listing all buckets is not required by this integration.

The application key ID maps to `B2_KEY_ID`; the application key secret maps to `B2_APPLICATION_KEY`. These are distinct values.

## Apply and test

1. Extract this patch into the project root, preserving its relative paths and allowing the two files to be replaced:
   - `config/settings.py`
   - `.env.example`
2. Copy the B2 variables above into the real root `.env` and supply the actual credentials locally.
3. Ensure `USE_S3_STORAGE` is not set to `true` at the same time. If it exists, set it to `false` or remove it.
4. The inspected `requirements.txt` already includes `django-storages==1.14.6` and `boto3==1.44.8`; no dependency change is required.
5. Run the local checks:

   ```powershell
   python manage.py check
   python manage.py check_b2_storage
   ```

6. Only after the local check succeeds, rebuild and recreate the Podman services so the web process and Celery worker load the new settings and `.env`:

   ```powershell
   podman compose up -d --build
   podman compose ps
   podman compose logs --tail 100 web celery-worker
   ```

7. Run the storage check inside the web container too:

   ```powershell
   podman compose exec web python manage.py check_b2_storage
   ```

   Then test from the worker container because ingestion runs asynchronously:

   ```powershell
   podman compose exec celery-worker python manage.py check_b2_storage
   ```

The Compose file already passes the root `.env` to `web`, `celery-worker`, and `celery-beat`; no Compose edit is needed for these settings.

## Important operational notes

- This patch does not alter PostgreSQL, models, migrations, pgvector, Celery task logic, or existing document records.
- Do not migrate old AWS objects automatically. The clean-slate database currently has zero knowledge documents, versions and chunks, so upload a fresh test document to B2 after the storage checks pass.
- Do not delete the old AWS bucket or revoke its key until you have confirmed no other deployment or data still depends on it.
- Do not remove the verified PostgreSQL backup until B2 storage and fresh-document ingestion/RAG tests have passed.
- B2 bucket-level SSE-B2 encryption can remain enabled. This configuration does not send an explicit per-object encryption header.
- The management command creates a uniquely named temporary object under `health-check/` and deletes it after successful verification.
