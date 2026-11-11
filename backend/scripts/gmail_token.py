"""One-time: get a GMAIL_REFRESH_TOKEN for the mailbox that sends HRMS email.

    cd backend && python -m scripts.gmail_token notifications@tesseractuk.in

Stop the local backend first: this listens on the port of the local
GOOGLE_REDIRECT_URI (already registered in Google Console) to receive the
sign-in. Sign in as the sending mailbox and approve "Send email on your
behalf". The printed token goes into Render as GMAIL_REFRESH_TOKEN — treat it
like a password. It stops working if that mailbox revokes access, changes
its password, or goes 6 months without the app sending anything.
"""
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt

from app import config
from app.gmail_api import SCOPE, TOKEN_URL

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.gmail_token <sending-mailbox@tesseractuk.in>")
    sender = sys.argv[1].strip().lower()
    redirect = config.GOOGLE_REDIRECT_URI
    parsed = urlparse(redirect)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        sys.exit(f"GOOGLE_REDIRECT_URI must be a localhost URL for this script, got {redirect}")
    if not (config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET):
        sys.exit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env first")

    state = secrets.token_urlsafe(24)
    url = AUTH_URL + "?" + urlencode({
        "client_id": config.GOOGLE_CLIENT_ID, "redirect_uri": redirect,
        "response_type": "code", "scope": f"openid email {SCOPE}",
        "access_type": "offline", "prompt": "consent", "login_hint": sender,
        "state": state,
    })
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] != state:
                self.send_response(400); self.end_headers()
                self.wfile.write(b"State mismatch - ignore this tab."); return
            result["code"] = q.get("code", [""])[0]
            result["error"] = q.get("error", [""])[0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"Done. You can close this tab and return to the terminal.")

        def log_message(self, *args):
            pass

    try:
        server = HTTPServer((parsed.hostname, parsed.port or 80), Handler)
    except OSError:
        sys.exit(f"Port {parsed.port} is busy - stop the local backend and run again.")
    print(f"Opening Google sign-in. Sign in as {sender}.\nIf no browser opens, visit:\n{url}\n")
    webbrowser.open(url)
    while "code" not in result:
        server.handle_request()
    server.server_close()
    if result["error"] or not result["code"]:
        sys.exit(f"Google returned an error: {result['error'] or 'no code'}")

    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": result["code"],
        "client_id": config.GOOGLE_CLIENT_ID, "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect,
    }, timeout=20)
    if resp.status_code != 200:
        sys.exit(f"Token exchange failed: {resp.status_code} {resp.text[:300]}")
    body = resp.json()
    # Came straight from Google over TLS, so reading the email claim is safe.
    email = jwt.decode(body["id_token"], options={"verify_signature": False}).get("email", "")
    if email.lower() != sender:
        sys.exit(f"You signed in as {email}, not {sender}. Run again and pick {sender}.")
    if SCOPE not in body.get("scope", "").split():
        sys.exit("The 'Send email on your behalf' permission was not granted. Run again and tick it.")
    if not body.get("refresh_token"):
        sys.exit("Google did not return a refresh token. Remove the app at "
                 "myaccount.google.com/permissions (as the mailbox) and run again.")
    print("Success. Set these on Render (never commit them):\n")
    print(f"EMAIL_BACKEND=gmail_api\nGMAIL_SENDER={sender}")
    print(f"GMAIL_REFRESH_TOKEN={body['refresh_token']}")


if __name__ == "__main__":
    main()
