"""
Services for creating knowledge-base documents and document versions.

Document identity is explicit:
- Creating a document always creates a new logical document.
- Creating a version requires an existing document ID.

The services store the original file and its metadata. They do not
perform text extraction, chunking, or embedding generation.
"""

import hashlib
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max

from apps.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)

import uuid


class DocumentUploadError(Exception):
    """Raised when a knowledge-base upload cannot be completed."""


def calculate_sha256(uploaded_file):
    """
    Calculate the SHA-256 checksum incrementally.

    Reading the file in chunks avoids loading the entire document
    into memory solely for checksum calculation.
    """
    original_position = uploaded_file.tell()
    checksum = hashlib.sha256()

    try:
        for chunk in uploaded_file.chunks():
            checksum.update(chunk)

        return checksum.hexdigest()

    finally:
        # Restore the position so Django's storage backend can read the file.
        uploaded_file.seek(original_position)


def _store_document_version(
    *,
    document,
    version_number,
    uploaded_file,
    uploaded_by,
):
    """
    Store one file and create its version record.

    The caller must execute this function inside transaction.atomic().
    The caller is also responsible for handling a transaction failure.
    """
    original_filename = Path(uploaded_file.name).name
    file_size = uploaded_file.size

    # The serializer will attach this value after validating the extension.
    file_type = getattr(uploaded_file, "validated_file_type", None)

    if not file_type:
        raise DocumentUploadError(
            "The uploaded file must pass serializer validation first."
        )

    checksum = calculate_sha256(uploaded_file)

    # Keep client-supplied filenames out of the storage directory structure.
    extension = Path(original_filename).suffix.lower()

    # Generate a unique storage name without exposing the original filename.
    storage_path = (
        f"knowledge/{document.id}/"
        f"v{version_number}/"
        f"{uuid.uuid4().hex}{extension}"
    )

    storage_key = None

    try:
        # Django's storage backend may adjust the name to avoid overwriting
        # an existing object. Always persist the returned storage key.
        storage_key = default_storage.save(storage_path, uploaded_file)

        version = KnowledgeDocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            storage_key=storage_key,
            checksum=checksum,
            uploaded_by=uploaded_by,
            processing_status=(
                KnowledgeDocumentVersion.ProcessingStatus.UPLOADED
            ),
        )

        return version, storage_key

    except Exception:
        # The database transaction cannot automatically roll back an
        # operation performed by a separate storage backend.
        if storage_key:
            try:
                default_storage.delete(storage_key)
            except Exception:
                # Preserve the original exception. Production logging
                # should record cleanup failures for investigation.
                pass

        raise


def create_knowledge_document(
    *,
    title,
    description,
    uploaded_file,
    uploaded_by,
):
    """
    Create a new logical document and its first uploaded version.

    A matching title does not cause an existing document to be reused.
    """
    storage_key = None

    try:
        with transaction.atomic():
            # Always create a new document identity, even if another
            # document already has the same title.
            document = KnowledgeDocument.objects.create(
                title=title,
                description=description or None,
                created_by=uploaded_by,
            )

            version, storage_key = _store_document_version(
                document=document,
                version_number=1,
                uploaded_file=uploaded_file,
                uploaded_by=uploaded_by,
            )

        return document, version

    except Exception as exc:
        # If the transaction fails after the file has been stored, remove
        # the file because database rollback cannot remove stored objects.
        if storage_key:
            try:
                default_storage.delete(storage_key)
            except Exception:
                pass

        if isinstance(exc, DocumentUploadError):
            raise

        raise DocumentUploadError(
            "The new knowledge-base document could not be created."
        ) from exc


def create_knowledge_document_version(
    *,
    document_id,
    uploaded_file,
    uploaded_by,
    description=None,
):
    """
    Add a new version to an explicitly identified document.

    The existing document is locked while the next version number
    is calculated, preventing concurrent updates from normally
    selecting the same version number.
    """
    storage_key = None

    try:
        with transaction.atomic():
            # Lock the existing document row before calculating its next
            # version. PostgreSQL supports this row-level locking behavior.
            document = (
                KnowledgeDocument.objects
                .select_for_update()
                .get(pk=document_id)
            )

            # Archived documents must not silently receive new versions.
            if document.status != KnowledgeDocument.Status.ACTIVE:
                raise DocumentUploadError(
                    "Cannot add a version to an archived document."
                )

            # Calculate the next version while holding the document lock.
            current_max = document.versions.aggregate(
                max_version=Max("version_number")
            )["max_version"]

            next_version = (current_max or 0) + 1

            # Update the description only when one was explicitly supplied.
            if description is not None:
                document.description = description or None
                document.save(
                    update_fields=["description", "updated_at"]
                )

            version, storage_key = _store_document_version(
                document=document,
                version_number=next_version,
                uploaded_file=uploaded_file,
                uploaded_by=uploaded_by,
            )

        return document, version

    except KnowledgeDocument.DoesNotExist as exc:
        raise DocumentUploadError(
            "The requested knowledge-base document does not exist."
        ) from exc

    except Exception as exc:
        # Clean up the stored object if the database transaction fails.
        if storage_key:
            try:
                default_storage.delete(storage_key)
            except Exception:
                pass

        if isinstance(exc, DocumentUploadError):
            raise

        raise DocumentUploadError(
            "The new document version could not be created."
        ) from exc