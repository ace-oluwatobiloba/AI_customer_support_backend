import uuid

from django.conf import settings
from django.db import models

# VectorField is provided by the pgvector Django integration,
# not by Django's built-in models module.
from pgvector.django import VectorField

class KnowledgeDocument(models.Model):
    """
    Represents the logical identity of a knowledge-base document.

    A document can have multiple uploaded versions. Keeping the logical
    document separate from its versions allows us to preserve history
    when an administrator uploads updated content.
    """

    class Status(models.TextChoices):
        # ACTIVE documents are available for use by the RAG system.
        ACTIVE = "ACTIVE", "Active"

        # ARCHIVED documents are retained for history but should not be
        # used as the current source of knowledge.
        ARCHIVED = "ARCHIVED", "Archived"

    # UUIDs prevent predictable sequential identifiers and remain
    # consistent with the rest of our project schema.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Human-readable name used by administrators when managing the
    # knowledge base.
    title = models.CharField(
        max_length=255,
    )

    # Optional description gives administrators additional context
    # about what information the document contains.
    description = models.TextField(
        blank=True,
        null=True,
    )

    # Records the user who originally added the logical document.
    # We use PROTECT so historical knowledge records are not accidentally
    # destroyed when a user account is removed.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="knowledge_documents",
    )

    # Controls whether this logical document remains available to the
    # active knowledge base.
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title


class KnowledgeDocumentVersion(models.Model):
    """
    Represents one uploaded version of a knowledge-base document.

    A logical document can have many versions. Each version represents
    a specific file that was uploaded and processed by the system.
    """

    class FileType(models.TextChoices):
        # Supported knowledge-base document formats from the SRS.
        PDF = "PDF", "PDF"
        DOCX = "DOCX", "DOCX"
        TXT = "TXT", "TXT"

    class ProcessingStatus(models.TextChoices):
        # The file has been uploaded but processing has not started.
        UPLOADED = "UPLOADED", "Uploaded"

        # A background worker is currently extracting and processing
        # the document.
        PROCESSING = "PROCESSING", "Processing"

        # Text extraction, chunking, and embedding generation completed.
        PROCESSED = "PROCESSED", "Processed"

        # Processing failed and requires investigation or retry.
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Each version belongs to one logical knowledge document.
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.PROTECT,
        related_name="versions",
    )

    # Allows us to distinguish Version 1, Version 2, Version 3, etc.
    version_number = models.PositiveIntegerField()

    # Stores the filename supplied when the document was uploaded.
    original_filename = models.CharField(
        max_length=255,
    )

    # Restricts uploaded files to the formats approved by the project.
    file_type = models.CharField(
        max_length=10,
        choices=FileType.choices,
    )

    # Stores the original file size in bytes.
    file_size = models.PositiveBigIntegerField()

    # Identifies where the actual file is stored.
    # The database stores the reference rather than the binary file itself.
    storage_key = models.CharField(
        max_length=500,
    )

    # A checksum allows us to detect duplicate or unchanged uploads.
    checksum = models.CharField(
        max_length=128,
    )

    # Tracks the document-processing pipeline.
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.UPLOADED,
        db_index=True,
    )

    # Records when document processing completes; NULL while unprocessed.
    processed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # Records which authenticated user uploaded this particular version.
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_knowledge_versions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        # Version numbers only need to be unique within their parent
        # document. Therefore, two different documents can both have
        # a Version 1.
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="unique_knowledge_document_version",
            ),
        ]

        # Newest versions appear first when querying a document's history.
        ordering = ["-version_number"]

    def __str__(self):
        return (
            f"{self.document.title} "
            f"v{self.version_number}"
        )


class DocumentChunk(models.Model):
    """
    Represents a searchable piece of a processed document version.

    RAG does not normally search an entire PDF or DOCX file at once.
    The extracted text is divided into smaller chunks, and each chunk
    receives an embedding for semantic vector search.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Every chunk belongs to exactly one processed document version.
    document_version = models.ForeignKey(
        KnowledgeDocumentVersion,
        on_delete=models.PROTECT,
        related_name="chunks",
    )

    # Determines the original position of this chunk within the document.
    # For example: 0, 1, 2, 3...
    chunk_index = models.PositiveIntegerField()

    # The actual extracted text that will eventually be supplied as
    # context to the AI model.
    content = models.TextField()

    # Approximate token count helps us control context size and monitor
    # the amount of text being sent to the embedding/LLM APIs.
    token_count = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # Flexible metadata can store information such as page number,
    # section heading, character offsets, or extraction information.
    metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
    )

    # Stores the 1536-dimensional embedding generated for this text chunk.
    # The dimension must match the embedding model configured for our RAG system.
    embedding = VectorField(
        dimensions=1536,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        # A chunk position must be unique within a document version.
        # This prevents two chunks from accidentally occupying the same
        # position in the source document.
        constraints = [
            models.UniqueConstraint(
                fields=["document_version", "chunk_index"],
                name="unique_document_chunk_index",
            ),
        ]

        # Returning chunks in their original document order makes
        # reconstruction and debugging easier.
        ordering = ["chunk_index"]

    def __str__(self):
        return (
            f"{self.document_version} "
            f"— chunk {self.chunk_index}"
        )