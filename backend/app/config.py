
"""Application configuration loaded from environment variables."""

import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
# Local test-only password auth. Production always disables this, even if the
# environment variable is accidentally set there.
DEV_PASSWORD_AUTH_ENABLED = (
    not IS_PRODUCTION
    and os.getenv("ENABLE_DEV_PASSWORD_AUTH", "false").strip().lower() == "true"
)

# Database: PostgreSQL in production (Render), SQLite fallback for local dev.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "" if IS_PRODUCTION else "sqlite:///./hrms.db",
).strip()

# Render provides postgres:// URLs; SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# HRMS application JWT settings.
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "" if IS_PRODUCTION else "change-me-in-production",
).strip()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
AUTH_SESSION_MAX_DAYS = int(os.getenv("AUTH_SESSION_MAX_DAYS", "7"))

# Frontend origins allowed to call the backend.
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "" if IS_PRODUCTION else "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

# Only accounts on these explicitly allowed email domains may sign in/create.
ALLOWED_EMAIL_DOMAINS = [
    domain.strip().lower().lstrip("@")
    for domain in os.getenv(
        "ALLOWED_EMAIL_DOMAINS",
        "" if IS_PRODUCTION else "tesseractuk.in",
    ).split(",")
    if domain.strip()
]

# Google OAuth configuration.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "" if IS_PRODUCTION else "http://localhost:8000/auth/google/callback",
).strip()
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "" if IS_PRODUCTION else "http://localhost:5173",
).strip().rstrip("/")

# Cookie settings for the HRMS session.
# Localhost uses HTTP during development. Production must use HTTPS.
COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE", "true" if IS_PRODUCTION else "false"
).strip().lower() == "true"
COOKIE_SAMESITE = os.getenv(
    "COOKIE_SAMESITE", "none" if IS_PRODUCTION else "lax"
).strip().lower()


def _require_https_url(name: str, value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError(f"Production setting {name} must be an HTTPS URL")


def _validate_production_config() -> None:
    """Fail startup when production auth/deployment settings are incomplete."""
    if not IS_PRODUCTION:
        return

    if not DATABASE_URL.startswith(("postgresql://", "postgresql+")):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL")
    if len(SECRET_KEY) < 32 or SECRET_KEY == "change-me-in-production":
        raise RuntimeError("Production requires a unique SECRET_KEY of at least 32 characters")
    if set(ALLOWED_EMAIL_DOMAINS) != {"tesseractuk.in"}:
        raise RuntimeError("Production ALLOWED_EMAIL_DOMAINS must be exactly tesseractuk.in")
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise RuntimeError("Production requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
    if not GOOGLE_REDIRECT_URI or not FRONTEND_URL or not CORS_ORIGINS:
        raise RuntimeError("Production requires GOOGLE_REDIRECT_URI, FRONTEND_URL, and CORS_ORIGINS")

    _require_https_url("GOOGLE_REDIRECT_URI", GOOGLE_REDIRECT_URI)
    _require_https_url("FRONTEND_URL", FRONTEND_URL)
    for origin in CORS_ORIGINS:
        _require_https_url("CORS_ORIGINS", origin)
        parsed = urlsplit(origin)
        if parsed.path or parsed.query or parsed.fragment:
            raise RuntimeError("Each production CORS_ORIGINS entry must be an origin only")

    if not COOKIE_SECURE or COOKIE_SAMESITE != "none":
        raise RuntimeError("Production Google SSO requires COOKIE_SECURE=true and COOKIE_SAMESITE=none")
    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
    if AUTH_SESSION_MAX_DAYS <= 0:
        raise RuntimeError("AUTH_SESSION_MAX_DAYS must be positive")
    if ACCESS_TOKEN_EXPIRE_MINUTES >= AUTH_SESSION_MAX_DAYS * 24 * 60:
        raise RuntimeError("Access tokens must expire before the refresh session")


_validate_production_config()

# File uploads.
UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "uploads",
    ),
)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

# Outbound email. "console" only logs messages (default until SMTP credentials
# exist); "smtp" sends through SMTP_HOST, e.g. smtp.gmail.com with an App
# Password for the notifications@ mailbox. "disabled" drops messages.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "console").strip().lower()
EMAIL_FROM = os.getenv("EMAIL_FROM", "Tesseract HRMS <notifications@tesseractuk.in>").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
if EMAIL_BACKEND not in {"console", "smtp", "disabled"}:
    raise RuntimeError("EMAIL_BACKEND must be console, smtp or disabled")
if EMAIL_BACKEND == "smtp" and not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
    raise RuntimeError("EMAIL_BACKEND=smtp requires SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD")

# Working-day rules (can be moved to company settings later).
STANDARD_WORK_HOURS = float(os.getenv("STANDARD_WORK_HOURS", "8"))
HALF_DAY_THRESHOLD_HOURS = float(
    os.getenv("HALF_DAY_THRESHOLD_HOURS", "4")
)
# Used only for employees with no shift assigned.
LATE_ARRIVAL_TIME = os.getenv("LATE_ARRIVAL_TIME", "09:30")
# Minutes after the employee's own shift start before they count as late.
LATE_GRACE_MINUTES = int(os.getenv("LATE_GRACE_MINUTES", "30"))
OFFICE_LATITUDE = float(os.getenv("OFFICE_LATITUDE", "22.72267583211552"))
OFFICE_LONGITUDE = float(os.getenv("OFFICE_LONGITUDE", "75.88714542620116"))
OFFICE_GEOFENCE_RADIUS_METERS = float(os.getenv("OFFICE_GEOFENCE_RADIUS_METERS", "500"))
MAX_GPS_ACCURACY_METERS = float(os.getenv("MAX_GPS_ACCURACY_METERS", "500"))
