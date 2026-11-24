"""Shared Celery dispatch helper for knowledge-document ingestion."""

import logging

from apps.knowledge.tasks import ingest_document_version

logger = logging.getLogger(__name__)


def dispatch_document_ingestion(version_id):
    """Queue ingestion and log broker failures without exposing internals."""
    try:
        ingest_document_version.delay(str(version_id))
    except Exception:
        logger.exception(
            "Could not queue ingestion for knowledge document version %s.",
            version_id,
        )
