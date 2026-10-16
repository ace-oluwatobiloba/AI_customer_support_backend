from django.core.files import File
from django.core.files.storage import default_storage


class DocumentStorageError(Exception):
    """Raised when a stored knowledge-base document cannot be accessed."""


def open_document(storage_key: str) -> File:
    """Open a stored document using Django's configured storage backend."""

    # Reject empty keys to prevent attempts to access an undefined file.
    if not storage_key or not storage_key.strip():
        raise DocumentStorageError(
            "A document storage key is required."
        )

    try:
        # Resolve the file through Django storage rather than using a local path.
        return default_storage.open(storage_key, mode="rb")

    except FileNotFoundError as exc:
        # Report missing documents with a consistent application exception.
        raise DocumentStorageError(
            "The requested knowledge-base document was not found."
        ) from exc

    except Exception as exc:
        # Normalize storage backend errors for callers.
        raise DocumentStorageError(
            "The knowledge-base document could not be opened."
        ) from exc