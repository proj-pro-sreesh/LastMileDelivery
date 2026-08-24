"""Email delivery providers: mock logger and Resend (https://resend.com)."""

import logging
import urllib.error
import urllib.request

logger = logging.getLogger("app.notifications")


class EmailProvider:
    def send(self, *, to: str, subject: str, body: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MockEmailProvider(EmailProvider):
    """Logs the email instead of sending — default for local development/tests."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("[MOCK EMAIL] to=%s subject=%s body=%s", to, subject, body)


class ResendEmailProvider(EmailProvider):
    """Sends via the Resend REST API. ``api_key`` is a Resend API key."""

    API_URL = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str, from_address: str):
        if not api_key or not from_address:
            raise ValueError("EMAIL_API_KEY and EMAIL_FROM are required when EMAIL_PROVIDER=resend")
        self._api_key = api_key
        self._from = from_address

    def send(self, *, to: str, subject: str, body: str) -> None:
        payload = _json_bytes({"from": self._from, "to": [to], "subject": subject, "text": body})
        request = urllib.request.Request(
            self.API_URL,
            data=payload,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Resend returned HTTP {response.status}")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Resend request failed: {exc}") from exc


def get_email_provider(*, provider_name: str, api_key: str, from_address: str) -> EmailProvider:
    if provider_name == "resend":
        return ResendEmailProvider(api_key=api_key, from_address=from_address)
    if provider_name == "mock":
        return MockEmailProvider()
    raise ValueError(f"Unknown EMAIL_PROVIDER {provider_name!r}; expected 'mock' or 'resend'")


def _json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")
