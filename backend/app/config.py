
"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

# Database: PostgreSQL in production (Render), SQLite fallback for local dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hrms.db")

# Render provides postgres:// URLs; SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# HRMS application JWT settings.
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
)

# Frontend origins allowed to call the backend.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

# Only accounts on these email domains may sign in or be created.
# Comma-separated; set to "*" to allow any domain.
ALLOWED_EMAIL_DOMAINS = [
    domain.strip().lower().lstrip("@")
    for domain in os.getenv(
        "ALLOWED_EMAIL_DOMAINS",
        "tesseractuk.in",
    ).split(",")
    if domain.strip()
]

# Google OAuth configuration.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback",
).strip()
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
).strip().rstrip("/")

# Cookie settings for the HRMS session.
# Localhost uses HTTP during development. Production must use HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()

# File uploads.
UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "uploads",
    ),
)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

# Working-day rules (can be moved to company settings later).
STANDARD_WORK_HOURS = float(os.getenv("STANDARD_WORK_HOURS", "8"))
HALF_DAY_THRESHOLD_HOURS = float(
    os.getenv("HALF_DAY_THRESHOLD_HOURS", "4")
)
LATE_ARRIVAL_TIME = os.getenv("LATE_ARRIVAL_TIME", "09:30")
