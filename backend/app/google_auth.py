
"""Google OAuth helpers for Tesseract HRMS.

Uses the existing httpx and PyJWT dependencies.
The OAuth callback and HRMS session creation are handled by auth.py.
"""

from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from .config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI


GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {
    "https://accounts.google.com",
    "accounts.google.com",
}

_jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)


def _check_google_configuration() -> None:
    """Fail clearly if local Google OAuth credentials are not configured."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured on the server",
        )

    if not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth redirect URI is not configured",
        )


def build_google_authorization_url(state: str) -> str:
    """Build Google's authorization URL for the login redirect."""
    _check_google_configuration()

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }

    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange Google's one-time authorization code for tokens."""
    _check_google_configuration()

    try:
        response = httpx.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not contact Google to complete sign-in",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Google sign-in could not be completed",
        )

    try:
        tokens = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google returned an invalid token response",
        ) from exc

    if not isinstance(tokens, dict) or not tokens.get("id_token"):
        raise HTTPException(
            status_code=401,
            detail="Google did not return an identity token",
        )

    return tokens


def verify_google_id_token(id_token: str) -> dict:
    """Verify Google's signed ID token and return its trusted claims."""
    _check_google_configuration()

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(id_token)

        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
            issuer=list(GOOGLE_ISSUERS),
            options={
                "require": ["exp", "iat", "iss", "sub", "aud"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Google identity token is invalid or expired",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not verify the Google identity token",
        ) from exc

    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=401,
            detail="Your Google account has no usable email address",
        )

    if claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=403,
            detail="Your Google email address must be verified",
        )

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=401,
            detail="Google did not provide a valid account identifier",
        )

    return claims
