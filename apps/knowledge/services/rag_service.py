from apps.knowledge.services.answer_service import (
    AnswerGenerationError,
    generate_grounded_answer,
)
from apps.knowledge.services.retrieval_service import (
    DEFAULT_RETRIEVAL_LIMIT,
    KnowledgeRetrievalError,
    retrieve_relevant_chunks,
)


class RAGServiceError(Exception):
    """Raised when the retrieval-augmented answer pipeline fails."""


def answer_question(
    question: str,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
) -> dict:
    """
    Retrieve relevant knowledge and generate a grounded support answer.

    Returns:
        {
            "answer": str,
            "sources": [
                {
                    "document_title": str,
                    "version_number": int | str,
                    "chunk_index": int | str,
                }
            ],
        }
    """
    try:
        chunks = retrieve_relevant_chunks(question, limit=limit)
    except KnowledgeRetrievalError as exc:
        raise RAGServiceError(
            "Could not retrieve relevant knowledge."
        ) from exc

    try:
        answer = generate_grounded_answer(question, chunks)
    except AnswerGenerationError as exc:
        import logging

        logging.getLogger(__name__).exception(
            "Answer generation failed in RAG service",
            exc_info=exc,
        )
        raise RAGServiceError(
            "Could not generate a grounded answer."
        ) from exc

    sources = []

    for chunk in chunks:
        document_version = getattr(chunk, "document_version", None)
        document = getattr(document_version, "document", None)

        sources.append(
            {
                "document_title": getattr(
                    document, "title", "Knowledge document"
                ),
                "version_number": getattr(
                    document_version, "version_number", "?"
                ),
                "chunk_index": getattr(chunk, "chunk_index", "?"),
            }
        )

    return {
        "answer": answer,
        "sources": sources,
    }
