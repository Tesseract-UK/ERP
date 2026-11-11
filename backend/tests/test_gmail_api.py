"""Gmail API mail backend: token exchange + send, against a mocked Google."""
import base64
import json
from email import message_from_bytes
from email.message import EmailMessage

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config, gmail_api


@pytest.fixture
def service_account(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    info = {"type": "service_account", "client_email": "hrms-mail@proj.iam.gserviceaccount.com",
            "private_key": pem}
    # Stored base64-encoded, as recommended for the Render env var.
    monkeypatch.setattr(config, "GMAIL_SERVICE_ACCOUNT_JSON",
                        base64.b64encode(json.dumps(info).encode()).decode())
    monkeypatch.setattr(config, "GMAIL_SENDER", "notifications@tesseractuk.in")
    monkeypatch.setitem(gmail_api._token, "value", None)
    return key.public_key()


def _patch_transport(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr(gmail_api.httpx, "Client",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def _message():
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = "HRMS <notifications@tesseractuk.in>", "a@tesseractuk.in", "Hi"
    m.set_content("Leave approved")
    return m


def test_sends_with_delegated_token_and_caches_it(service_account, monkeypatch):
    calls = {"token": 0, "send": []}

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            calls["token"] += 1
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            claims = jwt.decode(form["assertion"], service_account, algorithms=["RS256"],
                                audience=gmail_api.TOKEN_URL)
            assert claims["sub"] == "notifications@tesseractuk.in"  # impersonated mailbox
            assert claims["scope"] == gmail_api.SCOPE
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer tok"
        calls["send"].append(json.loads(request.content)["raw"])
        return httpx.Response(200, json={"id": "1"})

    _patch_transport(monkeypatch, handler)
    gmail_api.send(_message())
    gmail_api.send(_message())

    assert calls["token"] == 1  # cached between sends
    sent = message_from_bytes(base64.urlsafe_b64decode(calls["send"][0]))
    assert sent["To"] == "a@tesseractuk.in" and "Leave approved" in sent.get_payload()


def test_missing_delegation_raises_clear_error(service_account, monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(
        401, json={"error": "unauthorized_client"}))
    with pytest.raises(RuntimeError, match="unauthorized_client"):
        gmail_api.send(_message())


def test_mailer_swallows_gmail_failures(service_account, monkeypatch):
    from app import mailer
    monkeypatch.setattr(config, "EMAIL_BACKEND", "gmail_api")
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    mailer._deliver("a@tesseractuk.in", "Hi", "body")  # must not raise


def test_refresh_token_mode_needs_no_service_account(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_REFRESH_TOKEN", "1//refresh")
    monkeypatch.setattr(config, "GMAIL_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setitem(gmail_api._token, "value", None)
    seen = {}

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            seen.update(dict(x.split("=", 1) for x in request.content.decode().split("&")))
            return httpx.Response(200, json={"access_token": "tok2", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer tok2"
        return httpx.Response(200, json={"id": "1"})

    _patch_transport(monkeypatch, handler)
    gmail_api.send(_message())
    assert seen["grant_type"] == "refresh_token" and seen["client_id"] == "cid"
