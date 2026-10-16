import re
from dataclasses import dataclass

import tiktoken


# Define the initial chunking configuration.
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_ENCODING = "cl100k_base"


@dataclass(frozen=True)
class TextChunk:
    """Represent a text segment and its position in a document."""

    index: int
    content: str
    token_count: int


def normalize_text(text: str) -> str:
    """Normalize whitespace before splitting a document into chunks."""

    # Reject non-string inputs instead of silently converting their types.
    if not isinstance(text, str):
        raise TypeError("Text input must be a string.")

    # Remove NUL characters that can interfere with text processing.
    text = text.replace("\x00", "")

    # Collapse repeated whitespace while preserving word boundaries.
    text = re.sub(r"\s+", " ", text)

    # Remove whitespace from the beginning and end.
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    encoding_name: str = DEFAULT_ENCODING,
) -> list[TextChunk]:
    """Split text into token-bounded chunks with configurable overlap."""

    # Validate chunk configuration to prevent invalid or infinite loops.
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    # Normalize the text before tokenization.
    normalized_text = normalize_text(text)

    # Empty documents should produce no chunks.
    if not normalized_text:
        return []

    # Resolve the tokenizer used for token counting and chunk boundaries.
    try:
        encoding = tiktoken.get_encoding(encoding_name)
    except Exception as exc:
        raise ValueError(
            f"Unsupported or unavailable tokenizer encoding: {encoding_name}"
        ) from exc

    # Encode the complete document so chunk sizes are measured in tokens.
    tokens = encoding.encode(normalized_text)

    chunks = []
    start = 0
    chunk_index = 0

    # Advance through the token sequence while preserving configured overlap.
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))

        # Decode this token window back into readable text.
        chunk_content = encoding.decode(tokens[start:end]).strip()

        # Store only non-empty chunks.
        if chunk_content:
            chunks.append(
                TextChunk(
                    index=chunk_index,
                    content=chunk_content,
                    token_count=end - start,
                )
            )
            chunk_index += 1

        # Stop after the final chunk to avoid repeating the last window.
        if end == len(tokens):
            break

        # Move forward while retaining the requested overlap.
        start = end - chunk_overlap

    return chunks