"""Resend email backend, against a mocked Resend API."""
import json

import httpx

from app import config, mailer


def _patch(monkeypatch, handler):
    real_post = httpx.post

    def fake_post(url, **kw):
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            return c.post(url, **kw)
    monkeypatch.setattr(mailer.httpx, "post", fake_post)
    return real_post


def test_sends_via_resend(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test")
    sent = []

    def handler(request):
        assert request.url == mailer.RESEND_URL
        assert request.headers["authorization"] == "Bearer re_test"
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "abc"})

    _patch(monkeypatch, handler)
    mailer._deliver("a@tesseractuk.in", "Leave approved", "Your leave was approved.")
    assert sent == [{"from": config.EMAIL_FROM, "to": ["a@tesseractuk.in"],
                     "subject": "Leave approved", "text": "Your leave was approved."}]


def test_resend_failure_never_raises(monkeypatch, caplog):
    monkeypatch.setattr(config, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test")
    _patch(monkeypatch, lambda r: httpx.Response(403, json={"message": "domain is not verified"}))
    mailer._deliver("a@tesseractuk.in", "Hi", "body")  # must not raise
    assert "domain is not verified" in caplog.text
