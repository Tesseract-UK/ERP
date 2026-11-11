"""Send mail through the Gmail API over HTTPS (EMAIL_BACKEND=gmail_api).

Works on hosts that block outbound SMTP ports (e.g. Render's free tier).
Two ways to authenticate, checked in this order:

1. GMAIL_REFRESH_TOKEN (recommended, no admin rights needed): the sending
   mailbox signs in once with the app's existing Google OAuth client and grants
   only the gmail.send scope; `python -m scripts.gmail_token` prints the token.
2. GMAIL_SERVICE_ACCOUNT_JSON: a service account with Workspace domain-wide
   delegation for gmail.send, impersonating GMAIL_SENDER. Needs a super admin
   and an org that allows service-account keys.
"""
import base64
import json
import threading
import time
from email.message import EmailMessage

import httpx
import jwt

from . import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPE = "https://www.googleapis.com/auth/gmail.send"

_lock = threading.Lock()
_token: dict = {"value": None, "expires": 0.0}


def load_service_account(raw: str) -> dict:
    """Accept the key file's JSON either as-is or base64-encoded."""
    raw = raw.strip()
    if not raw.startswith("{"):
        raw = base64.b64decode(raw).decode("utf-8")
    info = json.loads(raw)
    for key in ("client_email", "private_key"):
        if not info.get(key):
            raise RuntimeError(f"GMAIL_SERVICE_ACCOUNT_JSON is missing '{key}'")
    return info


def _token_request() -> dict:
    if config.GMAIL_REFRESH_TOKEN:
        return {
            "grant_type": "refresh_token",
            "refresh_token": config.GMAIL_REFRESH_TOKEN,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
        }
    info = load_service_account(config.GMAIL_SERVICE_ACCOUNT_JSON)
    now = int(time.time())
    assertion = jwt.encode(
        {"iss": info["client_email"], "sub": config.GMAIL_SENDER, "scope": SCOPE,
         "aud": TOKEN_URL, "iat": now, "exp": now + 3600},
        info["private_key"], algorithm="RS256",
    )
    return {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}


def _access_token(client: httpx.Client) -> str:
    with _lock:
        if _token["value"] and time.time() < _token["expires"] - 60:
            return _token["value"]
        resp = client.post(TOKEN_URL, data=_token_request())
        if resp.status_code != 200:
            # invalid_grant = refresh token revoked/expired (re-run the script);
            # unauthorized_client = domain-wide delegation not set up.
            raise RuntimeError(f"Gmail token request failed: {resp.status_code} {resp.text[:300]}")
        body = resp.json()
        _token["value"] = body["access_token"]
        _token["expires"] = time.time() + int(body.get("expires_in", 3600))
        return _token["value"]


def send(message: EmailMessage) -> None:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    with httpx.Client(timeout=20) as client:
        token = _access_token(client)
        resp = client.post(SEND_URL, json={"raw": raw},
                           headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 401:  # token revoked/rotated: retry once fresh
            with _lock:
                _token["value"] = None
            token = _access_token(client)
            resp = client.post(SEND_URL, json={"raw": raw},
                               headers={"Authorization": f"Bearer {token}"})
        if resp.status_code >= 300:
            raise RuntimeError(f"Gmail send failed: {resp.status_code} {resp.text[:300]}")
