from django.db import transaction
from django.utils import timezone

from apps.knowledge.models import KnowledgeDocumentVersion
from apps.knowledge.services.chunk_persistence import save_document_chunks
from apps.knowledge.services.document_extractor import extract_text
from apps.knowledge.services.document_storage import open_document
from apps.knowledge.services.embedding_service import generate_embeddings
from apps.knowledge.services.text_chunker import chunk_text


class DocumentIngestionError(Exception):
    """Raised when document ingestion fails."""


def ingest_document(
    document_version: KnowledgeDocumentVersion,
) -> int:
    """Extract, chunk, embed, and persist a stored document version."""

    # Mark the document version as processing before starting the pipeline.
    document_version.processing_status = (
        KnowledgeDocumentVersion.ProcessingStatus.PROCESSING
    )
    document_version.save(
        update_fields=["processing_status", "updated_at"]
    )

    try:
        # Open the original file through Django's configured storage backend.
        with open_document(document_version.storage_key) as stored_file:
            extracted_text = extract_text(
                stored_file,
                filename=document_version.original_filename,
            )

        # Split the extracted text into token-aware chunks.
        chunks = chunk_text(extracted_text)

        # Reject documents that produce no usable chunks.
        if not chunks:
            raise DocumentIngestionError(
                "The document contains no usable text."
            )

        # Generate one embedding for each chunk.
        texts = [chunk.content for chunk in chunks]
        embeddings = generate_embeddings(texts)

        # Persist chunks and mark processing complete atomically.
        with transaction.atomic():
            save_document_chunks(
                document_version=document_version,
                chunks=chunks,
                embeddings=embeddings,
            )

            document_version.processing_status = (
                KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            )
            document_version.processed_at = timezone.now()

            document_version.save(
                update_fields=[
                    "processing_status",
                    "processed_at",
                    "updated_at",
                ]
            )

        return len(chunks)

    except Exception as exc:
        # Record the failed attempt for operational visibility.
        document_version.processing_status = (
            KnowledgeDocumentVersion.ProcessingStatus.FAILED
        )
        document_version.save(
            update_fields=["processing_status", "updated_at"]
        )

        # Preserve application-level ingestion errors.
        if isinstance(exc, DocumentIngestionError):
            raise

        # Normalize storage, extraction, embedding, and persistence failures.
        raise DocumentIngestionError(
            "Document ingestion failed."
        ) from exc