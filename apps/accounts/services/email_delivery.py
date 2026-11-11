"""Synchronous transactional email delivery through the Resend HTTP API."""

import logging
from html import escape

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when the configured transactional email provider rejects delivery."""


def send_mail(subject, message, from_email=None, recipient_list=None,
              fail_silently=False, html_message=None):
    """Django-compatible send_mail wrapper backed by Resend.

    Returns 1 on successful provider acceptance. Never logs API keys, message
    bodies, invitation tokens, or recipient addresses.
    """
    recipients = list(recipient_list or [])
    api_key = getattr(settings, "RESEND_API_KEY", "")
    sender = (from_email or settings.DEFAULT_FROM_EMAIL).strip()
    if not api_key:
        error = EmailDeliveryError(
            "RESEND_API_KEY is not configured; email was not sent."
        )
        if fail_silently:
            logger.warning("Transactional email skipped: Resend API key is missing.")
            return 0
        raise error

    payload = {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "text": message,
    }
    if html_message is None:
        safe_lines = "<br>".join(escape(line) for line in message.splitlines())
        html_message = (
            '<div style="font-family:Arial,sans-serif;line-height:1.6;'
            'color:#202938;max-width:600px;margin:0 auto;padding:24px">'
            '<div style="font-size:20px;font-weight:700;margin-bottom:20px">'
            'AI Customer Support</div>'
            f'<div>{safe_lines}</div>'
            '<p style="color:#687386;font-size:12px;margin-top:32px">'
            'This is an automated message. Please do not reply.</p></div>'
        )
    payload["html"] = html_message

    try:
        response = requests.post(
            settings.RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.RESEND_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(
            "Resend delivery request failed (exception_type=%s).",
            type(exc).__name__,
        )
        if fail_silently:
            return 0
        raise EmailDeliveryError(
            "The email provider could not accept the message."
        ) from exc

    logger.info("Resend accepted a transactional email (recipient_count=%s).",
                len(recipients))
    return 1
