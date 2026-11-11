
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.knowledge.services.answer_service import AnswerGenerationError
from apps.knowledge.services.rag_service import (
    RAGServiceError,
    answer_question,
)
from apps.knowledge.services.retrieval_service import KnowledgeRetrievalError


class RAGServiceTests(SimpleTestCase):
    def setUp(self):
        self.chunk = SimpleNamespace(
            chunk_index=4,
            document_version=SimpleNamespace(
                version_number=2,
                document=SimpleNamespace(title="Account Help"),
            ),
        )

    @patch("apps.knowledge.services.rag_service.generate_grounded_answer")
    @patch("apps.knowledge.services.rag_service.retrieve_relevant_chunks")
    def test_retrieves_generates_and_returns_sources(
        self, mock_retrieve, mock_generate
    ):
        mock_retrieve.return_value = [self.chunk]
        mock_generate.return_value = "You can update your account settings."

        result = answer_question("How do I update my account?")

        self.assertEqual(
            result["answer"],
            "You can update your account settings.",
        )
        self.assertEqual(
            result["sources"],
            [
                {
                    "document_title": "Account Help",
                    "version_number": 2,
                    "chunk_index": 4,
                }
            ],
        )
        mock_retrieve.assert_called_once_with(
            "How do I update my account?", limit=5
        )
        mock_generate.assert_called_once_with(
            "How do I update my account?", [self.chunk]
        )

    @patch("apps.knowledge.services.rag_service.generate_grounded_answer")
    @patch("apps.knowledge.services.rag_service.retrieve_relevant_chunks")
    def test_no_relevant_chunks_returns_answer_without_sources(
        self, mock_retrieve, mock_generate
    ):
        mock_retrieve.return_value = []
        mock_generate.return_value = (
            "I could not find relevant information. Contact support."
        )

        result = answer_question("A question outside the knowledge base")

        self.assertEqual(result["sources"], [])
        mock_generate.assert_called_once_with(
            "A question outside the knowledge base", []
        )

    @patch("apps.knowledge.services.rag_service.retrieve_relevant_chunks")
    def test_retrieval_failure_is_wrapped(self, mock_retrieve):
        mock_retrieve.side_effect = KnowledgeRetrievalError(
            "Embedding service unavailable"
        )

        with self.assertRaises(RAGServiceError) as context:
            answer_question("How do I update my account?")

        self.assertIsInstance(
            context.exception.__cause__,
            KnowledgeRetrievalError,
        )

    @patch("apps.knowledge.services.rag_service.generate_grounded_answer")
    @patch("apps.knowledge.services.rag_service.retrieve_relevant_chunks")
    def test_generation_failure_is_wrapped(
        self, mock_retrieve, mock_generate
    ):
        mock_retrieve.return_value = [self.chunk]
        mock_generate.side_effect = AnswerGenerationError(
            "AI provider unavailable"
        )

        with self.assertRaises(RAGServiceError) as context:
            answer_question("How do I update my account?")

        self.assertIsInstance(
            context.exception.__cause__,
            AnswerGenerationError,
        )

    @patch("apps.knowledge.services.rag_service.generate_grounded_answer")
    @patch("apps.knowledge.services.rag_service.retrieve_relevant_chunks")
    def test_custom_retrieval_limit_is_forwarded(
        self, mock_retrieve, mock_generate
    ):
        mock_retrieve.return_value = []
        mock_generate.return_value = "I don't have enough information."

        answer_question("Question", limit=3)

        mock_retrieve.assert_called_once_with("Question", limit=3)
