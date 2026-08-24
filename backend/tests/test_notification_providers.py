"""GAP 3: provider abstraction — mock/resend/twilio selection and failure isolation.

No network calls: real providers are exercised with monkeypatched transport.
"""

import logging

import pytest

from app.core.config import get_settings
from app.services import notification_service
from app.services.providers.email import MockEmailProvider, ResendEmailProvider, get_email_provider
from app.services.providers.sms import MockSmsProvider, TwilioSmsProvider, get_sms_provider
from tests.test_orders import ORDER_PAYLOAD


def test_mock_providers_log_email_and_sms(caplog):
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        MockEmailProvider().send(to="a@b.com", subject="Hi", body="Body")
        MockSmsProvider().send(to_phone="+911234567890", text="Hello")
    assert "[MOCK EMAIL]" in caplog.text and "a@b.com" in caplog.text
    assert "[MOCK SMS]" in caplog.text


def test_get_provider_factories():
    assert isinstance(get_email_provider(provider_name="mock", api_key="", from_address=""), MockEmailProvider)
    assert isinstance(get_sms_provider(provider_name="mock", api_key="", from_number=""), MockSmsProvider)
    with pytest.raises(ValueError):
        get_email_provider(provider_name="carrier-pigeon", api_key="", from_address="")
    with pytest.raises(ValueError):
        get_sms_provider(provider_name="smoke-signal", api_key="", from_number="")


def test_resend_requires_credentials():
    with pytest.raises(ValueError):
        ResendEmailProvider(api_key="", from_address="")
    provider = ResendEmailProvider(api_key="re_123", from_address="no-reply@lastmile.test")
    assert provider._api_key == "re_123"


def test_twilio_requires_sid_token_and_sender():
    with pytest.raises(ValueError):
        TwilioSmsProvider(api_key="only-sid", from_number="+15005550006")
    with pytest.raises(ValueError):
        TwilioSmsProvider(api_key="sid:token", from_number="")
    provider = TwilioSmsProvider(api_key="AC111:secret", from_number="+15005550006")
    assert provider._sid == "AC111" and provider._token == "secret"


def test_resend_send_builds_correct_request(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["data"] = request.data
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.email.urllib.request.urlopen", fake_urlopen)
    ResendEmailProvider(api_key="re_123", from_address="no-reply@lastmile.test").send(
        to="cust@example.com", subject="Delivered", body="Your parcel arrived"
    )
    assert captured["url"] == "https://api.resend.com/emails"
    assert b"cust@example.com" in captured["data"]
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["authorization"] == "Bearer re_123"


def test_twilio_send_uses_basic_auth_and_form_encoding(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["data"] = request.data
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.sms.urllib.request.urlopen", fake_urlopen)
    TwilioSmsProvider(api_key="AC111:secret", from_number="+15005550006").send(
        to_phone="+919000000000", text="Out for delivery"
    )
    assert "Accounts/AC111/Messages.json" in captured["url"]
    assert b"To=%2B919000000000" in captured["data"] or b"%2B919000000000" in captured["data"]
    import base64

    expected = base64.b64encode(b"AC111:secret").decode()
    assert captured["headers"]["authorization"] == f"Basic {expected}"


def test_failing_provider_does_not_break_order_transaction(
    client, db_session, pricing_world, customer_headers, admin_headers, monkeypatch
):
    """A raising email/SMS provider must not stop order flows or in-app persistence."""
    from sqlalchemy import select

    from app.models import Notification
    from tests.test_assignment import make_agent

    def boom(*args, **kwargs):
        raise RuntimeError("SMTP is on fire")

    monkeypatch.setattr(notification_service, "_dispatch_email", boom)
    monkeypatch.setattr(notification_service, "_dispatch_sms", boom)

    response = client.post("/orders", json=ORDER_PAYLOAD, headers=customer_headers)
    assert response.status_code == 201

    # Assignment triggers the first customer+agent notifications.
    agent = make_agent(db_session, lat="13.083000", lng="80.271000", zone_code="CHE-CEN")
    assign_response = client.post(
        f"/admin/orders/{response.json()['id']}/assign", json={"agent_id": agent["id"]}, headers=admin_headers
    )
    assert assign_response.status_code == 200

    # In-app rows still persisted even though both channels failed.
    kinds = [n.kind for n in db_session.scalars(select(Notification)).all()]
    assert "order.assigned" in kinds and "assignment.new" in kinds


def test_settings_expose_new_provider_fields():
    settings = get_settings()
    assert settings.email_provider in ("mock", "resend")
    assert settings.sms_provider in ("mock", "twilio")
