from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.test import SimpleTestCase

from apps.knowledge.services.embedding_service import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingGenerationError,
    generate_embeddings,
)


class EmbeddingServiceTests(SimpleTestCase):
    """Test embedding generation without calling the real Gemini API."""

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_generate_embeddings_returns_vectors_in_input_order(
        self, mock_client_class
    ):
        first_vector = [0.1] * EMBEDDING_DIMENSIONS
        second_vector = [0.2] * EMBEDDING_DIMENSIONS

        mock_response = SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=first_vector),
                SimpleNamespace(values=second_vector),
            ]
        )

        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-api-key"}):
            result = generate_embeddings(["First text", "Second text"])

        self.assertEqual(result, [first_vector, second_vector])

        mock_client.models.embed_content.assert_called_once_with(
            model=EMBEDDING_MODEL,
            contents=["First text", "Second text"],
            config=ANY,
        )

        config = mock_client.models.embed_content.call_args.kwargs["config"]
        self.assertEqual(
            config.output_dimensionality,
            EMBEDDING_DIMENSIONS,
        )

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_empty_input_returns_empty_list(self, mock_client_class):
        self.assertEqual(generate_embeddings([]), [])
        mock_client_class.assert_not_called()

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_blank_text_is_rejected(self, mock_client_class):
        with self.assertRaises(ValueError):
            generate_embeddings(["   "])

        mock_client_class.assert_not_called()

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_non_string_input_is_rejected(self, mock_client_class):
        with self.assertRaises(ValueError):
            generate_embeddings(["Valid text", 123])

        mock_client_class.assert_not_called()

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_missing_api_key_is_rejected(self, mock_client_class):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(EmbeddingGenerationError):
                generate_embeddings(["Example text"])

        mock_client_class.assert_not_called()

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_api_failure_raises_embedding_generation_error(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = RuntimeError(
            "Simulated provider failure"
        )
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-api-key"}):
            with self.assertRaises(EmbeddingGenerationError):
                generate_embeddings(["Example text"])

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_wrong_vector_dimensions_are_rejected(
        self, mock_client_class
    ):
        mock_response = SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[0.1] * 100),
            ]
        )

        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-api-key"}):
            with self.assertRaises(EmbeddingGenerationError):
                generate_embeddings(["Example text"])

    @patch("apps.knowledge.services.embedding_service.genai.Client")
    def test_unexpected_vector_count_is_rejected(
        self, mock_client_class
    ):
        mock_response = SimpleNamespace(
            embeddings=[
                SimpleNamespace(
                    values=[0.1] * EMBEDDING_DIMENSIONS,
                )
            ]
        )

        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-api-key"}):
            with self.assertRaises(EmbeddingGenerationError):
                generate_embeddings(["First text", "Second text"])
