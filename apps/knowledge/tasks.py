import logging
from celery import shared_task
from apps.knowledge.models import KnowledgeDocumentVersion
from apps.knowledge.services.ingestion_service import DocumentIngestionError, ingest_document

logger = logging.getLogger(__name__)
@shared_task(bind=True, name="knowledge.ingest_document_version", max_retries=3, default_retry_delay=60)
def ingest_document_version(self, version_id):
    try:
        version = KnowledgeDocumentVersion.objects.get(pk=version_id)
    except KnowledgeDocumentVersion.DoesNotExist:
        logger.warning("Knowledge document version not found: %s", version_id)
        return {"status": "not_found", "version_id": str(version_id)}
    try:
        count = ingest_document(version)
    except DocumentIngestionError as exc:
        logger.exception("Knowledge ingestion failed for version %s", version_id)
        raise self.retry(exc=exc)
    return {"status": "processed", "version_id": str(version_id), "chunk_count": count}
