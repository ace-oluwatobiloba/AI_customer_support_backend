import math

from django.db import transaction

from apps.knowledge.models import DocumentChunk, KnowledgeDocumentVersion


# Must match the dimensionality configured in embedding_service.py.
EMBEDDING_DIMENSIONS = 1536


class ChunkPersistenceError(Exception):
    """Raised when document chunks cannot be persisted."""


def save_document_chunks(
    document_version: KnowledgeDocumentVersion,
    chunks: list,
    embeddings: list[list[float]],
) -> list[DocumentChunk]:
    """Replace a document version's chunks atomically."""

    # Every chunk must have exactly one corresponding embedding.
    if len(chunks) != len(embeddings):
        raise ChunkPersistenceError(
            "The number of chunks must match the number of embeddings."
        )

    # Preserve the existing service contract for empty input.
    # The ingestion service separately rejects documents with no usable text.
    if not chunks:
        return []

    document_chunks = []

    for chunk, embedding in zip(chunks, embeddings):
        # Ensure each embedding has the dimensions expected by pgvector.
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ChunkPersistenceError(
                f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions; "
                f"received {len(embedding)}."
            )

        # Reject booleans, non-numeric values, NaN, and infinity.
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in embedding
        ):
            raise ChunkPersistenceError(
                "Embedding values must be finite numbers."
            )

        # Prepare replacement records before changing existing database data.
        document_chunks.append(
            DocumentChunk(
                document_version=document_version,
                chunk_index=chunk.index,
                content=chunk.content,
                token_count=chunk.token_count,
                metadata={},
                embedding=embedding,
            )
        )

    try:
        # Delete and recreate the chunks in one transaction.
        # If insertion fails, the deletion is rolled back as well.
        with transaction.atomic():
            DocumentChunk.objects.filter(
                document_version=document_version
            ).delete()

            # Insert the replacement chunks together.
            DocumentChunk.objects.bulk_create(document_chunks)

    except Exception as exc:
        # Wrap the error only after the transaction has rolled back.
        raise ChunkPersistenceError(
            "Failed to replace document chunks."
        ) from exc

    return document_chunks