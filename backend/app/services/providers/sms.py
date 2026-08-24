"""SMS delivery providers: mock logger and Twilio (https://www.twilio.com)."""

import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("app.notifications")


class SmsProvider:
    def send(self, *, to_phone: str, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MockSmsProvider(SmsProvider):
    """Logs the SMS instead of sending — default for local development/tests."""

    def send(self, *, to_phone: str, text: str) -> None:
        logger.info("[MOCK SMS] to=%s text=%s", to_phone, text)


class TwilioSmsProvider(SmsProvider):
    """Sends via the Twilio REST API.

    ``api_key`` must be formatted as ``AccountSid:AuthToken`` (colon-separated);
    ``from_number`` is a Twilio sender, e.g. ``+15005550006``.
    """

    API_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def __init__(self, *, api_key: str, from_number: str):
        sid, _, token = (api_key or "").partition(":")
        if not sid or not token or not from_number:
            raise ValueError(
                "SMS_API_KEY ('AccountSid:AuthToken') and SMS_FROM are required when SMS_PROVIDER=twilio"
            )
        self._sid = sid
        self._token = token
        self._from = from_number

    def send(self, *, to_phone: str, text: str) -> None:
        if not to_phone:
            raise RuntimeError("Recipient has no phone number on file")
        form = urllib.parse.urlencode({"From": self._from, "To": to_phone, "Body": text}).encode("utf-8")
        request = urllib.request.Request(
            self.API_URL_TEMPLATE.format(sid=self._sid),
            data=form,
            method="POST",
        )
        import base64

        credentials = base64.b64encode(f"{self._sid}:{self._token}".encode()).decode()
        request.add_header("Authorization", f"Basic {credentials}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Twilio returned HTTP {response.status}")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Twilio request failed: {exc}") from exc


def get_sms_provider(*, provider_name: str, api_key: str, from_number: str) -> SmsProvider:
    if provider_name == "twilio":
        return TwilioSmsProvider(api_key=api_key, from_number=from_number)
    if provider_name == "mock":
        return MockSmsProvider()
    raise ValueError(f"Unknown SMS_PROVIDER {provider_name!r}; expected 'mock' or 'twilio'")
