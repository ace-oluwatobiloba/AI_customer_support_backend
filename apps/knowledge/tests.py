from pathlib import Path
from django.db import IntegrityError
from django.test import TestCase
import tempfile
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase
from docx import Document
from pypdf import PdfWriter

from apps.accounts.models import User
from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)

from apps.knowledge.services.document_extractor import (
    DocumentExtractionError,
    extract_text,
)

from apps.knowledge.services.text_chunker import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    TextChunk,
    chunk_text,
    normalize_text,
)

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from apps.knowledge.services.chunk_persistence import (
    ChunkPersistenceError,
    save_document_chunks,
)
from apps.knowledge.services.ingestion_service import (
    DocumentIngestionError,
    ingest_document,
)

from apps.knowledge.services.text_chunker import TextChunk

User = get_user_model()

from unittest.mock import patch
from django.test import SimpleTestCase

# Provides in-memory content for testing Django's storage backend.
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Imports the storage abstraction and its application-level exception.
from apps.knowledge.services.document_storage import (
    DocumentStorageError,
    open_document,
)

# Provides in-memory file content for storage tests.
from django.core.files.base import ContentFile

# Uses the storage backend configured in Django settings.
from django.core.files.storage import default_storage

from apps.knowledge.services.upload_service import (
    DocumentUploadError,
    create_knowledge_document,
    create_knowledge_document_version,
)

class KnowledgeDocumentModelTest(TestCase):
    """Tests the logical knowledge-document model."""

    def setUp(self):
        # The document must have an authenticated user responsible
        # for creating it.
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

    def test_knowledge_document_creation(self):
        """A knowledge document can be created successfully."""
        document = KnowledgeDocument.objects.create(
            title="Refund Policy",
            description="Customer refund and cancellation policy.",
            created_by=self.admin,
        )

        self.assertIsNotNone(document.id)
        self.assertEqual(document.title, "Refund Policy")
        self.assertEqual(document.status, KnowledgeDocument.Status.ACTIVE)
        self.assertEqual(document.created_by, self.admin)

    def test_knowledge_document_reverse_relationship(self):
        """The creator can access documents through the reverse relation."""
        document = KnowledgeDocument.objects.create(
            title="Account Policy",
            created_by=self.admin,
        )

        self.assertIn(
            document,
            self.admin.knowledge_documents.all(),
        )

    def test_knowledge_document_timestamps(self):
        """Creation and update timestamps are automatically maintained."""
        document = KnowledgeDocument.objects.create(
            title="Support Guide",
            created_by=self.admin,
        )

        self.assertIsNotNone(document.created_at)
        self.assertIsNotNone(document.updated_at)


class KnowledgeDocumentVersionModelTest(TestCase):
    """Tests document versioning and its integrity constraints."""

    def setUp(self):
        # Versions belong to both a logical document and the user
        # who uploaded that particular file.
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

        self.document = KnowledgeDocument.objects.create(
            title="Refund Policy",
            created_by=self.admin,
        )

    def test_document_version_creation(self):
        """A document version can be created successfully."""
        version = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=102400,
            storage_key="knowledge/refund-policy/v1/refund-policy.pdf",
            checksum="abc123",
            uploaded_by=self.admin,
        )

        self.assertIsNotNone(version.id)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(
            version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.UPLOADED,
        )

    def test_multiple_versions_belong_to_one_document(self):
        """One logical document can contain multiple versions."""
        version_one = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1000,
            storage_key="knowledge/refund-policy/v1/file.pdf",
            checksum="checksum-v1",
            uploaded_by=self.admin,
        )

        version_two = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=2,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1200,
            storage_key="knowledge/refund-policy/v2/file.pdf",
            checksum="checksum-v2",
            uploaded_by=self.admin,
        )

        self.assertEqual(self.document.versions.count(), 2)
        self.assertEqual(version_one.version_number, 1)
        self.assertEqual(version_two.version_number, 2)

    def test_version_number_must_be_unique_per_document(self):
        """A document cannot contain two versions with the same number."""
        KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1000,
            storage_key="knowledge/refund-policy/v1/file.pdf",
            checksum="checksum-v1",
            uploaded_by=self.admin,
        )

        with self.assertRaises(IntegrityError):
            KnowledgeDocumentVersion.objects.create(
                document=self.document,
                version_number=1,
                original_filename="refund-policy.pdf",
                file_type=KnowledgeDocumentVersion.FileType.PDF,
                file_size=1000,
                storage_key="knowledge/refund-policy/v1/duplicate.pdf",
                checksum="checksum-duplicate",
                uploaded_by=self.admin,
            )

    def test_different_documents_can_have_same_version_number(self):
        """Version 1 can exist independently for different documents."""
        second_document = KnowledgeDocument.objects.create(
            title="Account Policy",
            created_by=self.admin,
        )

        version_one = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1000,
            storage_key="knowledge/refund-policy/v1/file.pdf",
            checksum="refund-v1",
            uploaded_by=self.admin,
        )

        version_two = KnowledgeDocumentVersion.objects.create(
            document=second_document,
            version_number=1,
            original_filename="account-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1000,
            storage_key="knowledge/account-policy/v1/file.pdf",
            checksum="account-v1",
            uploaded_by=self.admin,
        )

        self.assertEqual(version_one.version_number, 1)
        self.assertEqual(version_two.version_number, 1)


class DocumentChunkModelTest(TestCase):
    """Tests document chunks and vector storage."""

    def setUp(self):
        # Create the user responsible for the knowledge document.
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

        self.document = KnowledgeDocument.objects.create(
            title="Refund Policy",
            created_by=self.admin,
        )

        # A chunk belongs to a specific uploaded document version.
        self.version = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1000,
            storage_key="knowledge/refund-policy/v1/file.pdf",
            checksum="checksum-v1",
            uploaded_by=self.admin,
            processing_status=(
                KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            ),
        )

    def test_document_chunk_creation(self):
        """A document chunk can store text and a 1536-dimensional vector."""
        # This vector is deliberately small in meaning but complete in
        # dimensionality because our embedding field requires 1536 values.
        embedding = [0.0] * 1536

        chunk = DocumentChunk.objects.create(
            document_version=self.version,
            chunk_index=0,
            content="Customers may request a refund within 30 days.",
            token_count=9,
            metadata={
                "page": 1,
                "section": "Refund Eligibility",
            },
            embedding=embedding,
        )

        self.assertIsNotNone(chunk.id)
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.content, "Customers may request a refund within 30 days.")
        self.assertEqual(chunk.token_count, 9)
        self.assertEqual(chunk.metadata["page"], 1)

        # The vector field should contain exactly 1536 dimensions.
        self.assertEqual(len(chunk.embedding), 1536)

    def test_multiple_chunks_belong_to_one_version(self):
        """A processed version can contain multiple ordered chunks."""
        embedding = [0.0] * 1536

        first_chunk = DocumentChunk.objects.create(
            document_version=self.version,
            chunk_index=0,
            content="First section of the policy.",
            token_count=5,
            embedding=embedding,
        )

        second_chunk = DocumentChunk.objects.create(
            document_version=self.version,
            chunk_index=1,
            content="Second section of the policy.",
            token_count=5,
            embedding=embedding,
        )

        self.assertEqual(self.version.chunks.count(), 2)
        self.assertEqual(first_chunk.chunk_index, 0)
        self.assertEqual(second_chunk.chunk_index, 1)

    def test_chunk_index_must_be_unique_per_version(self):
        """Two chunks cannot occupy the same position in one version."""
        embedding = [0.0] * 1536

        DocumentChunk.objects.create(
            document_version=self.version,
            chunk_index=0,
            content="Original chunk.",
            token_count=3,
            embedding=embedding,
        )

        with self.assertRaises(IntegrityError):
            DocumentChunk.objects.create(
                document_version=self.version,
                chunk_index=0,
                content="Duplicate chunk position.",
                token_count=4,
                embedding=embedding,
            )

    def test_same_chunk_index_can_exist_in_different_versions(self):
        """Each document version maintains its own chunk numbering."""
        second_version = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=2,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=1200,
            storage_key="knowledge/refund-policy/v2/file.pdf",
            checksum="checksum-v2",
            uploaded_by=self.admin,
        )

        embedding = [0.0] * 1536

        first_version_chunk = DocumentChunk.objects.create(
            document_version=self.version,
            chunk_index=0,
            content="Version one chunk.",
            token_count=4,
            embedding=embedding,
        )

        second_version_chunk = DocumentChunk.objects.create(
            document_version=second_version,
            chunk_index=0,
            content="Version two chunk.",
            token_count=4,
            embedding=embedding,
        )

        self.assertEqual(first_version_chunk.chunk_index, 0)
        self.assertEqual(second_version_chunk.chunk_index, 0)


class KnowledgeIntegrationTest(TestCase):
    """Tests the complete document â†’ version â†’ chunk relationship."""

    def test_complete_knowledge_document_workflow(self):
        # The administrator creates the logical knowledge document.
        admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

        document = KnowledgeDocument.objects.create(
            title="Customer Refund Policy",
            description="Official refund policy used by the AI assistant.",
            created_by=admin,
        )

        # The first uploaded file becomes Version 1 of the document.
        version = KnowledgeDocumentVersion.objects.create(
            document=document,
            version_number=1,
            original_filename="refund-policy.pdf",
            file_type=KnowledgeDocumentVersion.FileType.PDF,
            file_size=2048,
            storage_key="knowledge/refund-policy/v1/refund-policy.pdf",
            checksum="sha256-example",
            uploaded_by=admin,
            processing_status=(
                KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            ),
        )

        # The processed version is divided into searchable chunks.
        embedding = [0.0] * 1536

        chunk = DocumentChunk.objects.create(
            document_version=version,
            chunk_index=0,
            content="Refunds are available within 30 days of purchase.",
            token_count=8,
            metadata={"page": 1},
            embedding=embedding,
        )

        # Verify the complete relationship chain.
        self.assertEqual(document.versions.count(), 1)
        self.assertEqual(version.chunks.count(), 1)
        self.assertEqual(chunk.document_version, version)
        self.assertEqual(chunk.document_version.document, document)
        self.assertEqual(chunk.document_version.document.created_by, admin)
        self.assertEqual(len(chunk.embedding), 1536)

class DocumentExtractorTests(SimpleTestCase):
    """Test extraction from supported document formats."""

    def setUp(self):
        # Create a temporary directory for test documents.
        self.temp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_directory.name)

    def tearDown(self):
        # Remove temporary files after each test.
        self.temp_directory.cleanup()

    def test_extract_text_from_txt(self):
        # Create a plain-text document with surrounding whitespace.
        file_path = self.directory / "sample.txt"
        file_path.write_text("  Knowledge base testing.  ", encoding="utf-8")

        # Verify extraction preserves the text while trimming its edges.
        self.assertEqual(extract_text(file_path), "Knowledge base testing.")

    def test_extract_text_from_docx(self):
        # Create a Word document containing a paragraph.
        file_path = self.directory / "sample.docx"
        document = Document()
        document.add_paragraph("Knowledge base from Word.")
        document.save(file_path)

        # Verify the paragraph is extracted correctly.
        self.assertEqual(
            extract_text(file_path),
            "Knowledge base from Word.",
        )

    def test_extract_text_from_docx_table(self):
        # Create a Word document containing text inside a table.
        file_path = self.directory / "table.docx"
        document = Document()
        table = document.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Information inside a table."
        document.save(file_path)

        # Verify table content is included in the extracted text.
        self.assertEqual(
            extract_text(file_path),
            "Information inside a table.",
        )

    def test_extract_text_from_pdf(self):
        # Create a valid but empty PDF to test empty-text rejection.
        file_path = self.directory / "empty.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)

        with file_path.open("wb") as pdf_file:
            writer.write(pdf_file)

        # Verify a PDF without extractable text raises the expected error.
        with self.assertRaises(DocumentExtractionError):
            extract_text(file_path)

    def test_unsupported_file_format_is_rejected(self):
        # Create a file with a format outside the supported list.
        file_path = self.directory / "sample.csv"
        file_path.write_text("id,name\n1,test", encoding="utf-8")

        # Verify unsupported formats are rejected.
        with self.assertRaises(DocumentExtractionError):
            extract_text(file_path)

    def test_missing_file_is_rejected(self):
        # Reference a path that does not exist.
        file_path = self.directory / "missing.txt"

        # Verify the service reports the missing document.
        with self.assertRaises(DocumentExtractionError):
            extract_text(file_path)

    def test_empty_txt_file_is_rejected(self):
        # Create an empty text document.
        file_path = self.directory / "empty.txt"
        file_path.write_text("", encoding="utf-8")

        # Verify documents without text are rejected.
        with self.assertRaises(DocumentExtractionError):
            extract_text(file_path)

class TextNormalizationTests(SimpleTestCase):
    """Test normalization of extracted document text."""

    def test_normalize_repeated_whitespace(self):
        # Collapse repeated spaces, tabs, and newlines into single spaces.
        result = normalize_text("  Hello   world!\n\nWelcome\tback.  ")

        self.assertEqual(result, "Hello world! Welcome back.")

    def test_normalize_removes_null_characters(self):
        # Remove NUL characters that may occur in extracted document text.
        result = normalize_text("Hello\x00 world")

        self.assertEqual(result, "Hello world")

    def test_normalize_empty_text(self):
        # Ensure whitespace-only input normalizes to an empty string.
        self.assertEqual(normalize_text("   \n\t  "), "")

    def test_normalize_rejects_non_string_input(self):
        # Require callers to supply text rather than unrelated data types.
        with self.assertRaises(TypeError):
            normalize_text(None)


class TextChunkingTests(SimpleTestCase):
    """Test token-aware document chunking."""

    def test_empty_text_returns_no_chunks(self):
        # Empty documents should not produce database-ready chunks.
        self.assertEqual(chunk_text(""), [])

    def test_whitespace_only_text_returns_no_chunks(self):
        # Normalization should eliminate whitespace-only content.
        self.assertEqual(chunk_text("   \n\t "), [])

    def test_short_text_produces_one_chunk(self):
        # Short text should fit inside a single chunk.
        result = chunk_text("This is a short document.")

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextChunk)
        self.assertEqual(result[0].index, 0)
        self.assertEqual(result[0].content, "This is a short document.")
        self.assertGreater(result[0].token_count, 0)

    def test_chunk_size_is_respected(self):
        # Generate enough text to require multiple chunks.
        text = " ".join(["knowledge"] * 1200)

        result = chunk_text(
            text,
            chunk_size=100,
            chunk_overlap=10,
        )

        # Confirm each chunk stays within the configured token limit.
        self.assertGreater(len(result), 1)

        for chunk in result:
            self.assertLessEqual(chunk.token_count, 100)

    def test_chunk_indices_are_sequential(self):
        # Chunk indices should start at zero and increase in document order.
        text = " ".join(["support"] * 500)

        result = chunk_text(
            text,
            chunk_size=80,
            chunk_overlap=10,
        )

        self.assertEqual(
            [chunk.index for chunk in result],
            list(range(len(result))),
        )

    def test_chunk_overlap_preserves_shared_tokens(self):
        # Use the same tokenizer to verify overlap between adjacent chunks.
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        text = " ".join(f"word{i}" for i in range(100))

        result = chunk_text(
            text,
            chunk_size=30,
            chunk_overlap=5,
        )

        self.assertGreater(len(result), 1)

        first_tokens = encoding.encode(result[0].content)
        second_tokens = encoding.encode(result[1].content)

        # The first five tokens of the second chunk should match the
        # last five tokens of the first chunk for this ASCII test input.
        self.assertEqual(first_tokens[-5:], second_tokens[:5])

    def test_invalid_chunk_size_is_rejected(self):
        # A zero-sized chunk cannot advance through the document.
        with self.assertRaises(ValueError):
            chunk_text("Example text", chunk_size=0)

    def test_negative_overlap_is_rejected(self):
        # Negative overlap is not a valid configuration.
        with self.assertRaises(ValueError):
            chunk_text("Example text", chunk_overlap=-1)

    def test_overlap_equal_to_chunk_size_is_rejected(self):
        # Overlap must be smaller than chunk size to guarantee progress.
        with self.assertRaises(ValueError):
            chunk_text(
                "Example text",
                chunk_size=10,
                chunk_overlap=10,
            )

    def test_default_configuration_is_valid(self):
        # Verify the initial defaults are internally consistent.
        self.assertGreater(DEFAULT_CHUNK_SIZE, 0)
        self.assertGreaterEqual(DEFAULT_CHUNK_OVERLAP, 0)
        self.assertLess(DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE)

class ChunkPersistenceTests(TestCase):
    """Test saving text chunks and their embeddings to PostgreSQL."""

    def setUp(self):
        # Create the user responsible for uploading the knowledge document.
        self.user = User.objects.create_user(
            email="chunk-persistence@example.com",
            password="TestPassword!123",
        )

        # Create the logical knowledge document.
        self.document = KnowledgeDocument.objects.create(
            title="Persistence Test Document",
            created_by=self.user,
        )

        # Create the uploaded version to which chunks will belong.
        self.document_version = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="sample.txt",
            file_type=KnowledgeDocumentVersion.FileType.TXT,
            file_size=100,
            storage_key="test/sample.txt",
            checksum="test-checksum-001",
            uploaded_by=self.user,
        )

    def make_embedding(self, value=0.1):
        # Generate a test vector with the required 1,536 dimensions.
        return [value] * 1536

    def test_save_document_chunks(self):
        # Prepare two chunks and their corresponding test embeddings.
        chunks = [
            TextChunk(
                index=0,
                content="First test chunk.",
                token_count=3,
            ),
            TextChunk(
                index=1,
                content="Second test chunk.",
                token_count=3,
            ),
        ]
        embeddings = [
            self.make_embedding(0.1),
            self.make_embedding(0.2),
        ]

        # Persist both chunks in the database.
        saved_chunks = save_document_chunks(
            self.document_version,
            chunks,
            embeddings,
        )

        # Verify the records and their essential fields.
        self.assertEqual(len(saved_chunks), 2)
        self.assertEqual(
            DocumentChunk.objects.filter(
                document_version=self.document_version
            ).count(),
            2,
        )

        first_chunk = DocumentChunk.objects.get(chunk_index=0)

        self.assertEqual(first_chunk.content, "First test chunk.")
        self.assertEqual(first_chunk.token_count, 3)
        self.assertEqual(
            first_chunk.document_version,
            self.document_version,
        )

    def test_empty_chunk_list_returns_empty_list(self):
        # Empty input should not create database records.
        result = save_document_chunks(
            self.document_version,
            [],
            [],
        )

        self.assertEqual(result, [])
        self.assertEqual(DocumentChunk.objects.count(), 0)

    def test_mismatched_chunk_and_embedding_counts_are_rejected(self):
        # Every chunk must have exactly one embedding.
        chunks = [
            TextChunk(index=0, content="A test chunk.", token_count=3),
        ]

        with self.assertRaises(ChunkPersistenceError):
            save_document_chunks(
                self.document_version,
                chunks,
                [],
            )

        # Validation should occur before any database writes.
        self.assertEqual(DocumentChunk.objects.count(), 0)

    def test_invalid_embedding_dimensions_are_rejected(self):
        # A vector with the wrong dimensions must never be persisted.
        chunks = [
            TextChunk(index=0, content="A test chunk.", token_count=3),
        ]
        invalid_embedding = [0.1] * 100

        with self.assertRaises(ChunkPersistenceError):
            save_document_chunks(
                self.document_version,
                chunks,
                [invalid_embedding],
            )

        self.assertEqual(DocumentChunk.objects.count(), 0)

    def test_non_numeric_embedding_values_are_rejected(self):
        # Embeddings must contain numeric values rather than strings.
        chunks = [
            TextChunk(index=0, content="A test chunk.", token_count=3),
        ]
        invalid_embedding = [0.1] * 1535 + ["invalid"]

        with self.assertRaises(ChunkPersistenceError):
            save_document_chunks(
                self.document_version,
                chunks,
                [invalid_embedding],
            )

        self.assertEqual(DocumentChunk.objects.count(), 0)

    def test_duplicate_chunk_indices_roll_back_the_transaction(self):
        # Duplicate indices violate the database uniqueness constraint.
        chunks = [
            TextChunk(index=0, content="First chunk.", token_count=2),
            TextChunk(index=0, content="Duplicate index.", token_count=2),
        ]
        embeddings = [
            self.make_embedding(0.1),
            self.make_embedding(0.2),
        ]

        # The database error should be translated into our service error.
        with self.assertRaises(ChunkPersistenceError):
            save_document_chunks(
                self.document_version,
                chunks,
                embeddings,
            )

        # Atomicity means neither chunk should remain in the database.
        self.assertEqual(
            DocumentChunk.objects.filter(
                document_version=self.document_version
            ).count(),
            0,
        )

class DocumentIngestionServiceTests(TestCase):
    """Test coordination of the document ingestion pipeline."""

    def setUp(self):
        # Create the user responsible for uploading the document.
        self.user = User.objects.create_user(
            email="ingestion-test@example.com",
            password="TestPassword!123",
        )

        # Create the logical knowledge-base document.
        self.document = KnowledgeDocument.objects.create(
            title="Ingestion Test Document",
            created_by=self.user,
        )

        # Prepare sample content for the ingestion tests.
        self.sample_content = (
            "This is a sample document for ingestion testing."
        )

        # Save the sample file through Django's configured storage.
        # The returned name is the storage key used by the application.
        self.storage_key = default_storage.save(
            f"test-uploads/{uuid.uuid4().hex}-sample.txt",
            ContentFile(self.sample_content.encode("utf-8")),
        )

        # Create a document version referencing the storage key.
        self.document_version = KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            original_filename="sample.txt",
            file_type=KnowledgeDocumentVersion.FileType.TXT,
            file_size=len(self.sample_content.encode("utf-8")),
            storage_key=self.storage_key,
            checksum="ingestion-test-checksum",
            uploaded_by=self.user,
        )

    def tearDown(self):
        # Remove the stored test file after each test.
        if default_storage.exists(self.storage_key):
            default_storage.delete(self.storage_key)

    @patch(
        "apps.knowledge.services.ingestion_service.save_document_chunks"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.generate_embeddings"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.chunk_text"
    )
    def test_successful_ingestion(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
        mock_save_document_chunks,
    ):
        # Provide a predictable chunk without testing the chunker itself.
        mock_chunk_text.return_value = [
            TextChunk(
                index=0,
                content="Sample ingested content.",
                token_count=3,
            )
        ]

        # Use a valid-shaped embedding without calling OpenAI.
        mock_generate_embeddings.return_value = [[0.1] * 1536]

        # Execute the ingestion pipeline.
        result = ingest_document(self.document_version)

        # Confirm that the extracted text reaches the chunking stage.
        mock_chunk_text.assert_called_once_with(self.sample_content)

        # Confirm that the embedding and persistence stages are called.
        mock_generate_embeddings.assert_called_once_with(
            ["Sample ingested content."]
        )
        mock_save_document_chunks.assert_called_once()

        # Confirm that the service reports the number of chunks.
        self.assertEqual(result, 1)

        # Confirm that the document version is marked as processed.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.PROCESSED,
        )

    @patch(
        "apps.knowledge.services.ingestion_service.generate_embeddings"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.chunk_text"
    )
    def test_empty_document_content_fails(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
    ):
        # Simulate extraction that produces no usable chunks.
        mock_chunk_text.return_value = []

        # Empty content must fail before embedding generation.
        with self.assertRaises(DocumentIngestionError):
            ingest_document(self.document_version)

        mock_generate_embeddings.assert_not_called()

        # Confirm that the failed attempt is recorded.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.FAILED,
        )

    @patch(
        "apps.knowledge.services.ingestion_service.generate_embeddings"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.chunk_text"
    )
    def test_embedding_failure_marks_document_failed(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
    ):
        # Supply one chunk so ingestion reaches embedding generation.
        mock_chunk_text.return_value = [
            TextChunk(
                index=0,
                content="Sample content.",
                token_count=2,
            )
        ]

        # Simulate a failure from the embedding provider.
        mock_generate_embeddings.side_effect = RuntimeError(
            "Simulated embedding failure"
        )

        # The service should expose its domain-specific exception.
        with self.assertRaises(DocumentIngestionError):
            ingest_document(self.document_version)

        # Confirm that the document version is marked as failed.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.FAILED,
        )

        # Confirm that no chunks were persisted.
        self.assertEqual(DocumentChunk.objects.count(), 0)

    def test_missing_document_file_marks_document_failed(self):
        # Generate a storage key that does not correspond to a stored file.
        missing_key = (
            f"test-uploads/missing-{uuid.uuid4().hex}.txt"
        )

        # Point the document version at the nonexistent object.
        self.document_version.storage_key = missing_key
        self.document_version.save(update_fields=["storage_key"])

        # Confirm that the fixture really refers to a missing file.
        self.assertFalse(default_storage.exists(missing_key))

        # Ingestion should fail when the document cannot be opened.
        with self.assertRaises(DocumentIngestionError):
            ingest_document(self.document_version)

        # Confirm that the failed attempt is recorded.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.FAILED,
        )

    @patch(
        "apps.knowledge.services.ingestion_service.generate_embeddings"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.chunk_text"
    )
    def test_successful_ingestion_sets_processed_at(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
    ):
        mock_chunk_text.return_value = [
            TextChunk(
                index=0,
                content="Password reset instructions.",
                token_count=3,
            )
        ]
        mock_generate_embeddings.return_value = [[0.3] * 1536]

        self.document_version.processed_at = None
        self.document_version.save(update_fields=["processed_at"])

        result = ingest_document(self.document_version)

        self.assertEqual(result, 1)

        self.document_version.refresh_from_db()

        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.PROCESSED,
        )
        self.assertIsNotNone(self.document_version.processed_at)
    @patch(
        "apps.knowledge.services.ingestion_service.generate_embeddings"
    )
    @patch(
        "apps.knowledge.services.ingestion_service.chunk_text"
    )
    def test_reprocessing_replaces_existing_chunks(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
    ):
        # Create a chunk from a previous successful ingestion.
        DocumentChunk.objects.create(
            document_version=self.document_version,
            chunk_index=0,
            content="Old document content.",
            token_count=3,
            metadata={},
            embedding=[0.2] * 1536,
        )

        # Provide new content and a valid-shaped embedding.
        mock_chunk_text.return_value = [
            TextChunk(
                index=0,
                content="New document content.",
                token_count=3,
            )
        ]
        mock_generate_embeddings.return_value = [[0.3] * 1536]

        # Run ingestion again for the same document version.
        result = ingest_document(self.document_version)

        # The service should report one replacement chunk.
        self.assertEqual(result, 1)

        # The previous chunk should be replaced, not duplicated.
        chunks = DocumentChunk.objects.filter(
            document_version=self.document_version
        )
        self.assertEqual(chunks.count(), 1)
        self.assertEqual(
            chunks.first().content,
            "New document content.",
        )

        # Confirm that reprocessing succeeds.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.PROCESSED,
        )

    @patch("apps.knowledge.services.ingestion_service.generate_embeddings")
    @patch("apps.knowledge.services.ingestion_service.chunk_text")
    def test_embedding_failure_preserves_existing_chunks(
        self,
        mock_chunk_text,
        mock_generate_embeddings,
    ):
        # Create a previously indexed chunk that must survive a failed retry.
        DocumentChunk.objects.create(
            document_version=self.document_version,
            chunk_index=0,
            content="Previously indexed content.",
            token_count=3,
            metadata={},
            embedding=[0.1] * 1536,
        )

        # Allow processing to reach the embedding stage.
        mock_chunk_text.return_value = [
            TextChunk(
                index=0,
                content="Replacement content.",
                token_count=2,
            )
        ]

        # Simulate an embedding-provider failure during the retry.
        mock_generate_embeddings.side_effect = RuntimeError(
            "Simulated embedding failure"
        )

        # The ingestion service should report a consistent application error.
        with self.assertRaises(DocumentIngestionError):
            ingest_document(self.document_version)

        # Verify that the original chunk remains unchanged.
        self.assertEqual(
            DocumentChunk.objects.filter(
                document_version=self.document_version
            ).count(),
            1,
        )
        self.assertEqual(
            DocumentChunk.objects.get(
                document_version=self.document_version
            ).content,
            "Previously indexed content.",
        )

        # Verify that the failed processing attempt is recorded.
        self.document_version.refresh_from_db()
        self.assertEqual(
            self.document_version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.FAILED,
        )

    def test_persistence_failure_rolls_back_chunk_replacement(self):
        # Create an existing chunk that should survive a failed replacement.
        DocumentChunk.objects.create(
            document_version=self.document_version,
            chunk_index=0,
            content="Previously indexed content.",
            token_count=3,
            metadata={},
            embedding=[0.1] * 1536,
        )

        # Prepare a replacement chunk with a different index and content.
        replacement_chunks = [
            TextChunk(
                index=1,
                content="Replacement content.",
                token_count=2,
            )
        ]

        # Supply a correctly sized embedding for the replacement chunk.
        replacement_embeddings = [[0.2] * 1536]

        # Simulate a database failure after the deletion has been attempted.
        with patch(
            "apps.knowledge.services.chunk_persistence.DocumentChunk.objects.bulk_create",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(ChunkPersistenceError):
                save_document_chunks(
                    document_version=self.document_version,
                    chunks=replacement_chunks,
                    embeddings=replacement_embeddings,
                )

        # Verify that the transaction restored the original chunk.
        self.assertEqual(
            DocumentChunk.objects.filter(
                document_version=self.document_version
            ).count(),
            1,
        )
        self.assertEqual(
            DocumentChunk.objects.get(
                document_version=self.document_version
            ).content,
            "Previously indexed content.",
        )

class DocumentStorageServiceTests(SimpleTestCase):
    """Test document access through Django's storage abstraction."""

    def setUp(self):
        # Generate a unique key to avoid collisions with other test files.
        self.storage_key = (
            f"test-uploads/storage-test-{uuid.uuid4().hex}.txt"
        )

        self.sample_content = b"Knowledge base storage test."

        # Save the sample document through Django's configured backend.
        self.saved_key = default_storage.save(
            self.storage_key,
            ContentFile(self.sample_content),
        )

    def tearDown(self):
        # Remove the stored file so test artifacts do not accumulate.
        if default_storage.exists(self.saved_key):
            default_storage.delete(self.saved_key)

    def test_open_document_reads_stored_content(self):
        # Open the document using its storage key.
        with open_document(self.saved_key) as stored_file:
            content = stored_file.read()

        # Confirm that the stored bytes are returned unchanged.
        self.assertEqual(content, self.sample_content)

    def test_open_document_rejects_empty_storage_key(self):
        # An empty key must fail before accessing the storage backend.
        with self.assertRaises(DocumentStorageError):
            open_document("")

    def test_open_document_rejects_whitespace_storage_key(self):
        # Whitespace-only keys must also be rejected.
        with self.assertRaises(DocumentStorageError):
            open_document("   ")

    def test_open_document_rejects_missing_file(self):
        # Generate a key that does not identify an existing file.
        missing_key = (
            f"test-uploads/missing-{uuid.uuid4().hex}.txt"
        )

        self.assertFalse(default_storage.exists(missing_key))

        # Missing files must produce the application's storage exception.
        with self.assertRaises(DocumentStorageError):
            open_document(missing_key)

class KnowledgeDocumentUploadServiceTests(TestCase):
    """
    Test knowledge-document creation, explicit identity, versioning,
    and storage cleanup.
    """

    def setUp(self):
        # Create an administrator who owns the uploaded documents.
        self.admin = User.objects.create_user(
            email="knowledge-admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

        # Track only the files created by this test instance.
        self.storage_keys = []

    def tearDown(self):
        # Delete test-created files without affecting unrelated storage objects.
        for storage_key in self.storage_keys:
            if default_storage.exists(storage_key):
                default_storage.delete(storage_key)

    def make_uploaded_file(self, name, content):
        """Create an in-memory upload with a validated file type."""

        uploaded_file = ContentFile(
            content.encode("utf-8"),
            name=name,
        )

        # Simulate the file-type value assigned by the upload serializer.
        extension = name.rsplit(".", 1)[-1].lower()

        file_types = {
            "pdf": KnowledgeDocumentVersion.FileType.PDF,
            "docx": KnowledgeDocumentVersion.FileType.DOCX,
            "txt": KnowledgeDocumentVersion.FileType.TXT,
        }

        if extension not in file_types:
            raise ValueError(f"Unsupported test file extension: {extension}")

        uploaded_file.validated_file_type = file_types[extension]

        return uploaded_file

    def track_version_file(self, version):
        """Register a stored file for cleanup after the test."""
        self.storage_keys.append(version.storage_key)

    def test_creates_new_document_with_first_version(self):
        """A new document receives its own identity and version 1."""

        document, version = create_knowledge_document(
            title="Refund Policy",
            description="Refund and cancellation rules.",
            uploaded_file=self.make_uploaded_file(
                "refund-policy.txt",
                "Customers may request a refund.",
            ),
            uploaded_by=self.admin,
        )

        self.track_version_file(version)

        self.assertEqual(document.title, "Refund Policy")
        self.assertEqual(version.document_id, document.id)
        self.assertEqual(version.version_number, 1)

        self.assertEqual(
            version.processing_status,
            KnowledgeDocumentVersion.ProcessingStatus.UPLOADED,
        )

        self.assertTrue(
            default_storage.exists(version.storage_key)
        )

    def test_same_title_creates_distinct_document_identities(self):
        """Two new documents can share a title without sharing identity."""

        document_one, version_one = create_knowledge_document(
            title="Customer Policy",
            description="First policy.",
            uploaded_file=self.make_uploaded_file(
                "policy-one.txt",
                "First policy content.",
            ),
            uploaded_by=self.admin,
        )

        self.track_version_file(version_one)

        document_two, version_two = create_knowledge_document(
            title="Customer Policy",
            description="Second policy.",
            uploaded_file=self.make_uploaded_file(
                "policy-two.txt",
                "Second policy content.",
            ),
            uploaded_by=self.admin,
        )

        self.track_version_file(version_two)

        self.assertNotEqual(document_one.id, document_two.id)

        self.assertEqual(version_one.version_number, 1)
        self.assertEqual(version_two.version_number, 1)

        self.assertEqual(
            KnowledgeDocument.objects.filter(
                title="Customer Policy"
            ).count(),
            2,
        )

    def test_explicit_document_identity_creates_next_version(self):
        """A version upload updates the specified document's history."""

        document, version_one = create_knowledge_document(
            title="Account Policy",
            description="Original account policy.",
            uploaded_file=self.make_uploaded_file(
                "account-policy.txt",
                "Original policy content.",
            ),
            uploaded_by=self.admin,
        )

        self.track_version_file(version_one)

        updated_document, version_two = (
            create_knowledge_document_version(
                document_id=document.id,
                uploaded_file=self.make_uploaded_file(
                    "account-policy-v2.txt",
                    "Updated policy content.",
                ),
                uploaded_by=self.admin,
            )
        )

        self.track_version_file(version_two)

        # The logical document retains its original identity.
        self.assertEqual(updated_document.id, document.id)
        self.assertEqual(version_two.document_id, document.id)

        # The new version number follows the existing version.
        self.assertEqual(version_two.version_number, 2)

        # The first version remains available.
        self.assertTrue(
            KnowledgeDocumentVersion.objects.filter(
                pk=version_one.pk,
                version_number=1,
            ).exists()
        )

        self.assertEqual(document.versions.count(), 2)

    def test_missing_document_id_raises_upload_error(self):
        """A missing document must not silently create a new identity."""

        import uuid

        with self.assertRaises(DocumentUploadError):
            create_knowledge_document_version(
                document_id=uuid.uuid4(),
                uploaded_file=self.make_uploaded_file(
                    "policy.txt",
                    "Policy content.",
                ),
                uploaded_by=self.admin,
            )

        # No document should be created by a failed version upload.
        self.assertEqual(
            KnowledgeDocument.objects.count(),
            0,
        )

    def test_archived_document_rejects_new_version(self):
        """Archived documents cannot receive additional versions."""

        document, version = create_knowledge_document(
            title="Archived Policy",
            description="Policy retained for history.",
            uploaded_file=self.make_uploaded_file(
                "archived-policy.txt",
                "Archived policy content.",
            ),
            uploaded_by=self.admin,
        )

        self.track_version_file(version)

        document.status = KnowledgeDocument.Status.ARCHIVED
        document.save(update_fields=["status", "updated_at"])

        with self.assertRaises(DocumentUploadError):
            create_knowledge_document_version(
                document_id=document.id,
                uploaded_file=self.make_uploaded_file(
                    "archived-policy-v2.txt",
                    "Replacement content.",
                ),
                uploaded_by=self.admin,
            )

        # The failed request must not create another version.
        self.assertEqual(document.versions.count(), 1)

    def test_database_failure_removes_uploaded_file(self):
        """A database failure must trigger cleanup of the stored file."""

        with patch(
            "apps.knowledge.services.upload_service."
            "KnowledgeDocumentVersion.objects.create",
            side_effect=RuntimeError("Simulated database failure"),
        ):
            with self.assertRaises(DocumentUploadError):
                create_knowledge_document(
                    title="Failure Test",
                    description="Testing storage cleanup.",
                    uploaded_file=self.make_uploaded_file(
                        "failure-policy.txt",
                        "Content for the failure test.",
                    ),
                    uploaded_by=self.admin,
                )

        # The database transaction should roll back the new document.
        self.assertFalse(
            KnowledgeDocument.objects.filter(
                title="Failure Test"
            ).exists()
        )

        # The storage backend should contain no file for this failed upload.
        self.assertEqual(
            default_storage.listdir("knowledge")[1]
            if default_storage.exists("knowledge")
            else [],
            [],
        )

class KnowledgeDocumentUploadAPITests(TestCase):
    """
    HTTP-level tests for knowledge-base document upload endpoints.

    These tests verify routing, authentication, authorization,
    request validation, and the responses returned by the API.
    """

    def setUp(self):
        # Use DRF's APIClient to send requests through the HTTP layer.
        from rest_framework.test import APIClient

        self.client = APIClient()

        # Create an administrator authorized to manage knowledge documents.
        self.admin = User.objects.create_user(
            email="kb-admin@example.com",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
        )

        # Create a customer who must not be allowed to manage the KB.
        self.customer = User.objects.create_user(
            email="kb-customer@example.com",
            password="StrongPassword123!",
            role=User.Role.CUSTOMER,
        )

        # Define the endpoints under test.
        self.documents_url = "/api/v1/knowledge/documents/"

        # Authenticate as the administrator for tests that need permission.
        self.client.force_authenticate(user=self.admin)

        # Track stored files so every test can clean up after itself.
        self.created_storage_keys = []

    def tearDown(self):
        # Remove files created during API requests.
        from django.core.files.storage import default_storage

        for storage_key in self.created_storage_keys:
            if default_storage.exists(storage_key):
                default_storage.delete(storage_key)

    def make_file(self, name="policy.txt", content=b"Knowledge base policy."):
        # Create an in-memory uploaded file for multipart requests.
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            name=name,
            content=content,
            content_type="text/plain",
        )

    def record_document_files(self, document):
        # Track storage keys belonging to a document for test cleanup.
        for version in document.versions.all():
            self.created_storage_keys.append(version.storage_key)

    def test_unauthenticated_user_cannot_upload_document(self):
        """Anonymous users must be rejected."""

        # Remove the authenticated administrator from the test client.
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.documents_url,
            {
                "title": "Support Policy",
                "file": self.make_file(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)

    def test_customer_cannot_upload_document(self):
        """Only active administrators may manage knowledge documents."""

        # Authenticate as a customer rather than an administrator.
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.documents_url,
            {
                "title": "Support Policy",
                "file": self.make_file(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)

    def test_admin_can_create_document(self):
        """A valid administrator upload creates a document and version 1."""

        response = self.client.post(
            self.documents_url,
            {
                "title": "Support Policy",
                "description": "Customer support guidelines.",
                "file": self.make_file(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)

        # Verify that the API returned the expected document metadata.
        self.assertIn("document", response.data)
        self.assertIn("version", response.data)
        self.assertEqual(
            response.data["document"]["title"],
            "Support Policy",
        )
        self.assertEqual(
            response.data["version"]["version_number"],
            1,
        )
        self.assertEqual(
            response.data["version"]["processing_status"],
            KnowledgeDocumentVersion.ProcessingStatus.UPLOADED,
        )

        # Confirm the database contains the new logical document.
        document = KnowledgeDocument.objects.get(
            pk=response.data["document"]["id"]
        )

        self.assertEqual(document.versions.count(), 1)

        # Clean up the stored file after the test.
        self.record_document_files(document)

    def test_unsupported_file_format_is_rejected(self):
        """The API must reject unsupported extensions."""

        response = self.client.post(
            self.documents_url,
            {
                "title": "Unsupported Document",
                "file": self.make_file(
                    name="malware.exe",
                    content=b"not an allowed document",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)

    def test_admin_can_create_next_document_version(self):
        """The version endpoint must preserve earlier versions."""

        # Create the original document through the public API.
        create_response = self.client.post(
            self.documents_url,
            {
                "title": "Refund Policy",
                "file": self.make_file(
                    name="refund-policy.txt",
                    content=b"Original refund policy.",
                ),
            },
            format="multipart",
        )

        self.assertEqual(create_response.status_code, 201)

        document_id = create_response.data["document"]["id"]

        # Retrieve the new document so its stored file can be cleaned up.
        document = KnowledgeDocument.objects.get(pk=document_id)
        self.record_document_files(document)

        # Upload a replacement version using the explicit document ID.
        version_url = (
            f"/api/v1/knowledge/documents/{document_id}/versions/"
        )

        version_response = self.client.post(
            version_url,
            {
                "file": self.make_file(
                    name="refund-policy-v2.txt",
                    content=b"Updated refund policy.",
                ),
            },
            format="multipart",
        )

        self.assertEqual(version_response.status_code, 201)
        self.assertEqual(
            version_response.data["version"]["version_number"],
            2,
        )

        # Confirm the original version remains available.
        document.refresh_from_db()

        self.assertEqual(document.versions.count(), 2)

        self.assertTrue(
            document.versions.filter(version_number=1).exists()
        )
        self.assertTrue(
            document.versions.filter(version_number=2).exists()
        )

        # Track the newly created file as well.
        self.record_document_files(document)

    def test_missing_document_returns_404(self):
        """A version cannot be created for a nonexistent document."""

        # A random UUID should not match any existing document.
        missing_document_id = uuid.uuid4()

        version_url = (
            f"/api/v1/knowledge/documents/"
            f"{missing_document_id}/versions/"
        )

        response = self.client.post(
            version_url,
            {
                "file": self.make_file(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)
