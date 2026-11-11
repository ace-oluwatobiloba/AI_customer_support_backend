
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.knowledge.services.answer_service import (
    AnswerGenerationError,
    DEFAULT_GENERATION_MODEL,
    SYSTEM_INSTRUCTION,
    generate_grounded_answer,
)


class AnswerServiceTests(SimpleTestCase):
    def setUp(self):
        self.chunk = SimpleNamespace(
            content="Customers can request a refund within 14 days.",
            chunk_index=2,
            document_version=SimpleNamespace(
                version_number=3,
                document=SimpleNamespace(title="Refund Policy"),
            ),
        )

    def test_empty_question_is_rejected(self):
        for question in ("", "   ", None, 123):
            with self.subTest(question=question):
                with self.assertRaises(ValueError):
                    generate_grounded_answer(question, [self.chunk])

    def test_empty_chunks_return_fallback_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            answer = generate_grounded_answer("What is the refund policy?", [])

        self.assertIn("support agent", answer)

    def test_chunks_without_usable_content_return_fallback(self):
        unusable_chunk = SimpleNamespace(
            content="   ",
            chunk_index=0,
            document_version=None,
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "apps.knowledge.services.answer_service.genai.Client"
            ) as mock_client:
                answer = generate_grounded_answer(
                    "What is the refund policy?",
                    [unusable_chunk],
                )

        self.assertIn("support agent", answer)
        mock_client.assert_not_called()

    def test_successful_generation_uses_context_and_configuration(self):
        expected_answer = "Customers can request a refund within 14 days."

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key"},
            clear=True,
        ):
            with patch(
                "apps.knowledge.services.answer_service.genai.Client"
            ) as mock_client_factory:
                mock_client_factory.return_value.models.generate_content.return_value = (
                    SimpleNamespace(text=f"  {expected_answer}  ")
                )

                answer = generate_grounded_answer(
                    "How long do I have to request a refund?",
                    [self.chunk],
                )

        self.assertEqual(answer, expected_answer)
        mock_client_factory.assert_called_once_with(api_key="test-key")

        call_kwargs = (
            mock_client_factory.return_value.models.generate_content.call_args.kwargs
        )
        self.assertEqual(call_kwargs["model"], DEFAULT_GENERATION_MODEL)
        self.assertIn("Refund Policy", call_kwargs["contents"])
        self.assertIn("version 3", call_kwargs["contents"])
        self.assertIn("chunk 2", call_kwargs["contents"])
        self.assertIn(self.chunk.content, call_kwargs["contents"])
        self.assertIn(
            "How long do I have to request a refund?",
            call_kwargs["contents"],
        )
        self.assertEqual(
            call_kwargs["config"].system_instruction,
            SYSTEM_INSTRUCTION,
        )
        self.assertEqual(call_kwargs["config"].temperature, 0.2)

    def test_missing_api_key_raises_generation_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "apps.knowledge.services.answer_service.genai.Client"
            ) as mock_client:
                with self.assertRaises(AnswerGenerationError):
                    generate_grounded_answer(
                        "What is the refund policy?",
                        [self.chunk],
                    )

        mock_client.assert_not_called()

    def test_provider_failure_is_wrapped(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key"},
            clear=True,
        ):
            with patch(
                "apps.knowledge.services.answer_service.genai.Client"
            ) as mock_client_factory:
                mock_client_factory.return_value.models.generate_content.side_effect = (
                    RuntimeError("Simulated provider failure")
                )

                with self.assertRaises(AnswerGenerationError):
                    generate_grounded_answer(
                        "What is the refund policy?",
                        [self.chunk],
                    )

    def test_empty_provider_response_is_rejected(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key"},
            clear=True,
        ):
            with patch(
                "apps.knowledge.services.answer_service.genai.Client"
            ) as mock_client_factory:
                mock_client_factory.return_value.models.generate_content.return_value = (
                    SimpleNamespace(text="   ")
                )

                with self.assertRaises(AnswerGenerationError):
                    generate_grounded_answer(
                        "What is the refund policy?",
                        [self.chunk],
                    )
