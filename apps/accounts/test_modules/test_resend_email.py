from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.accounts.services.email_delivery import (
    EmailDeliveryError,
    send_mail,
)


@override_settings(
    RESEND_API_KEY="re_test_key",
    RESEND_API_URL="https://api.resend.com/emails",
    RESEND_TIMEOUT=7,
    DEFAULT_FROM_EMAIL="onboarding@resend.dev",
)
class ResendEmailDeliveryTests(SimpleTestCase):
    @patch("apps.accounts.services.email_delivery.requests.post")
    def test_sends_resend_request_with_expected_headers_and_payload(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        post.return_value = response

        result = send_mail(
            subject="Invitation",
            message="Your invitation token is secret.",
            recipient_list=["delivered@resend.dev"],
        )

        self.assertEqual(result, 1)
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.resend.com/emails")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test_key")
        self.assertEqual(kwargs["timeout"], 7)
        self.assertEqual(kwargs["json"]["from"], "onboarding@resend.dev")
        self.assertEqual(kwargs["json"]["to"], ["delivered@resend.dev"])
        self.assertIn("Your invitation token is secret.", kwargs["json"]["text"])
        self.assertIn("<div", kwargs["json"]["html"])

    @override_settings(RESEND_API_KEY="")
    @patch("apps.accounts.services.email_delivery.requests.post")
    def test_missing_api_key_fails_without_network_request(self, post):
        with self.assertRaises(EmailDeliveryError):
            send_mail("Subject", "Body", recipient_list=["test@example.com"])
        post.assert_not_called()

    @patch("apps.accounts.services.email_delivery.requests.post")
    def test_provider_http_error_is_wrapped(self, post):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("provider rejected")
        post.return_value = response

        with self.assertRaises(EmailDeliveryError):
            send_mail("Subject", "Body", recipient_list=["test@example.com"])

    @patch("apps.accounts.services.email_delivery.requests.post")
    def test_network_error_is_wrapped(self, post):
        post.side_effect = requests.Timeout("timed out")

        with self.assertRaises(EmailDeliveryError):
            send_mail("Subject", "Body", recipient_list=["test@example.com"])
