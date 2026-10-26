import os

from google import genai
from google.genai import types


EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingGenerationError(Exception):
    """Raised when text embeddings cannot be generated."""


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate Gemini embeddings for a batch of text strings."""

    if not texts:
        return []

    if not all(isinstance(text, str) and text.strip() for text in texts):
        raise ValueError("Every input must be a non-empty string.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise EmbeddingGenerationError(
            "Gemini API key is not configured."
        )

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )

        if not response.embeddings:
            raise EmbeddingGenerationError(
                "The embedding API returned no vectors."
            )

        embeddings = [
            embedding.values
            for embedding in response.embeddings
        ]

        if len(embeddings) != len(texts):
            raise EmbeddingGenerationError(
                "The embedding API returned an unexpected number of vectors."
            )

        if any(
            embedding is None
            or len(embedding) != EMBEDDING_DIMENSIONS
            for embedding in embeddings
        ):
            raise EmbeddingGenerationError(
                "The embedding API returned an unexpected vector dimension."
            )

        return embeddings

    except EmbeddingGenerationError:
        raise
    except Exception as exc:
        raise EmbeddingGenerationError(
            "Failed to generate text embeddings."
        ) from exc
