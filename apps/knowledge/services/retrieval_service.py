import math

from django.db.models import F, OuterRef, Subquery
from pgvector.django import CosineDistance

from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocumentVersion,
)
from apps.knowledge.services.embedding_service import generate_embeddings


DEFAULT_RETRIEVAL_LIMIT = 5
MAX_RETRIEVAL_LIMIT = 20
EMBEDDING_DIMENSIONS = 1536


class KnowledgeRetrievalError(Exception):
    """Raised when a knowledge retrieval request cannot be completed."""


def _eligible_chunks():
    """
    Return chunks from the latest successfully processed version
    of each active knowledge document.

    If a newer version is still processing or has failed, the most
    recent successfully processed version remains eligible.
    """

    latest_processed_version = (
        KnowledgeDocumentVersion.objects.filter(
            document_id=OuterRef("document_version__document_id"),
            processing_status=(
                KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            ),
        )
        .order_by("-version_number")
        .values("pk")[:1]
    )

    return (
        DocumentChunk.objects.filter(
            document_version__document__status="ACTIVE",
            document_version__processing_status=(
                KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            ),
        )
        .annotate(
            latest_processed_version_id=Subquery(
                latest_processed_version
            )
        )
        .filter(
            document_version_id=F("latest_processed_version_id")
        )
    )


def retrieve_relevant_chunks(
    query: str,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
) -> list[DocumentChunk]:
    """
    Find the most semantically relevant eligible knowledge chunks.

    Returned chunks are ordered by ascending cosine distance.
    Smaller cosine distance means a closer vector match.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("The search query must be a non-empty string.")

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_RETRIEVAL_LIMIT
    ):
        raise ValueError(
            f"Limit must be an integer between 1 and "
            f"{MAX_RETRIEVAL_LIMIT}."
        )

    eligible_chunks = _eligible_chunks()

    # Avoid a paid embedding request when no searchable knowledge exists.
    if not eligible_chunks.exists():
        return []

    try:
        embeddings = generate_embeddings([query.strip()])
    except Exception as exc:
        raise KnowledgeRetrievalError(
            "Failed to generate the search query embedding."
        ) from exc

    if len(embeddings) != 1:
        raise KnowledgeRetrievalError(
            "The embedding service returned an unexpected vector count."
        )

    query_embedding = embeddings[0]

    if len(query_embedding) != EMBEDDING_DIMENSIONS:
        raise KnowledgeRetrievalError(
            f"Expected a {EMBEDDING_DIMENSIONS}-dimensional query embedding."
        )

    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in query_embedding
    ):
        raise KnowledgeRetrievalError(
            "The query embedding contains invalid numeric values."
        )

    try:
        return list(
            eligible_chunks.annotate(
                cosine_distance=CosineDistance(
                    "embedding",
                    query_embedding,
                )
            )
            .order_by("cosine_distance", "pk")[:limit]
        )
    except Exception as exc:
        raise KnowledgeRetrievalError(
            "Failed to search the knowledge base."
        ) from exc
