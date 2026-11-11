
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.knowledge.models import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from apps.knowledge.services.retrieval_service import (
    KnowledgeRetrievalError,
    retrieve_relevant_chunks,
)

User = get_user_model()


class KnowledgeRetrievalTests(TestCase):
    """Test semantic retrieval against PostgreSQL and pgvector."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="retrieval-test@example.com",
            password="TestPassword!123",
        )

        self.document = KnowledgeDocument.objects.create(
            title="Customer Support Policy",
            created_by=self.user,
        )

        self.version = self.create_version(1)

        # Query vector points along the first dimension.
        self.query_embedding = [1.0] + [0.0] * 1535

    def create_version(self, number, status=None):
        return KnowledgeDocumentVersion.objects.create(
            document=self.document,
            version_number=number,
            original_filename="support-policy.txt",
            file_type=KnowledgeDocumentVersion.FileType.TXT,
            file_size=100,
            storage_key=f"test/support-policy/v{number}.txt",
            checksum=f"retrieval-checksum-{number}",
            uploaded_by=self.user,
            processing_status=(
                status
                or KnowledgeDocumentVersion.ProcessingStatus.PROCESSED
            ),
        )

    def create_chunk(self, version, content, embedding, index=0):
        return DocumentChunk.objects.create(
            document_version=version,
            chunk_index=index,
            content=content,
            token_count=5,
            embedding=embedding,
        )

    @patch(
        "apps.knowledge.services.retrieval_service.generate_embeddings"
    )
    def test_results_are_ranked_by_cosine_distance(
        self, mock_generate_embeddings
    ):
        relevant = self.create_chunk(
            self.version,
            "Refunds are available within 30 days.",
            self.query_embedding,
        )

        less_relevant_embedding = [0.0, 1.0] + [0.0] * 1534
        self.create_chunk(
            self.version,
            "Our office opens at nine.",
            less_relevant_embedding,
            index=1,
        )

        mock_generate_embeddings.return_value = [
            self.query_embedding
        ]

        results = retrieve_relevant_chunks("What is the refund policy?")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, relevant.id)
        mock_generate_embeddings.assert_called_once_with(
            ["What is the refund policy?"]
        )

    @patch(
        "apps.knowledge.services.retrieval_service.generate_embeddings"
    )
    def test_only_latest_processed_version_is_searched(
        self, mock_generate_embeddings
    ):
        old_chunk = self.create_chunk(
            self.version,
            "Old refund policy.",
            self.query_embedding,
        )

        latest_version = self.create_version(2)
        latest_chunk = self.create_chunk(
            latest_version,
            "Updated refund policy.",
            self.query_embedding,
        )

        mock_generate_embeddings.return_value = [
            self.query_embedding
        ]

        results = retrieve_relevant_chunks("refund policy")

        result_ids = {chunk.id for chunk in results}
        self.assertIn(latest_chunk.id, result_ids)
        self.assertNotIn(old_chunk.id, result_ids)

    @patch(
        "apps.knowledge.services.retrieval_service.generate_embeddings"
    )
    def test_previous_processed_version_remains_searchable_while_newer_version_processes(
        self, mock_generate_embeddings
    ):
        old_chunk = self.create_chunk(
            self.version,
            "Previously processed support policy.",
            self.query_embedding,
        )

        self.create_version(
            2,
            KnowledgeDocumentVersion.ProcessingStatus.PROCESSING,
        )

        mock_generate_embeddings.return_value = [
            self.query_embedding
        ]

        results = retrieve_relevant_chunks("support policy")

        self.assertEqual([chunk.id for chunk in results], [old_chunk.id])

    @patch(
        "apps.knowledge.services.retrieval_service.generate_embeddings"
    )
    def test_archived_document_is_not_searched(
        self, mock_generate_embeddings
    ):
        self.create_chunk(
            self.version,
            "Archived support policy.",
            self.query_embedding,
        )

        self.document.status = KnowledgeDocument.Status.ARCHIVED
        self.document.save(update_fields=["status"])

        results = retrieve_relevant_chunks("support policy")

        self.assertEqual(results, [])
        mock_generate_embeddings.assert_not_called()

    @patch(
        "apps.knowledge.services.retrieval_service.generate_embeddings"
    )
    def test_embedding_failure_is_wrapped(
        self, mock_generate_embeddings
    ):
        self.create_chunk(
            self.version,
            "Support policy.",
            self.query_embedding,
        )

        mock_generate_embeddings.side_effect = RuntimeError(
            "Simulated embedding provider failure"
        )

        with self.assertRaises(KnowledgeRetrievalError):
            retrieve_relevant_chunks("support policy")

    def test_blank_query_is_rejected(self):
        with self.assertRaises(ValueError):
            retrieve_relevant_chunks("   ")

    def test_invalid_limit_is_rejected(self):
        for invalid_limit in (0, -1, 21, True, 1.5, "5"):
            with self.subTest(limit=invalid_limit):
                with self.assertRaises(ValueError):
                    retrieve_relevant_chunks(
                        "support policy",
                        limit=invalid_limit,
                    )
