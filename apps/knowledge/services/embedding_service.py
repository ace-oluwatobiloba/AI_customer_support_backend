from openai import OpenAI


# Define the embedding model approved for the project.
EMBEDDING_MODEL = "text-embedding-3-small"

# Keep the vector dimensions consistent with DocumentChunk.embedding.
EMBEDDING_DIMENSIONS = 1536


class EmbeddingGenerationError(Exception):
    """Raised when text embeddings cannot be generated."""


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of text strings."""

    # Return immediately when there is no text to embed.
    if not texts:
        return []

    # Reject invalid input before making an external API request.
    if not all(isinstance(text, str) and text.strip() for text in texts):
        raise ValueError("Every input must be a non-empty string.")

    try:
        # Create the client using OPENAI_API_KEY from the environment.
        client = OpenAI()

        # Request embeddings in one batch to reduce API overhead.
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
        )

        # Sort results by their original input positions.
        ordered_results = sorted(response.data, key=lambda item: item.index)

        # Extract vectors in the same order as the input strings.
        embeddings = [
            item.embedding
            for item in ordered_results
        ]

        # Ensure every returned vector matches the database schema.
        if len(embeddings) != len(texts):
            raise EmbeddingGenerationError(
                "The embedding API returned an unexpected number of vectors."
            )

        if any(
            len(embedding) != EMBEDDING_DIMENSIONS
            for embedding in embeddings
        ):
            raise EmbeddingGenerationError(
                "The embedding API returned an unexpected vector dimension."
            )

        return embeddings

    except EmbeddingGenerationError:
        # Preserve validation errors raised by this service.
        raise
    except Exception as exc:
        # Hide provider details behind a consistent application exception.
        raise EmbeddingGenerationError(
            "Failed to generate text embeddings."
        ) from exc