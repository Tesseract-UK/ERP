"""Application configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# Database: PostgreSQL in production (Render), SQLite fallback for local dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hrms.db")
# Render provides postgres:// URLs; SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Comma-separated list of allowed frontend origins (Vercel URL in production).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"))
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

# Working-day rules (can be moved to company settings later).
STANDARD_WORK_HOURS = float(os.getenv("STANDARD_WORK_HOURS", "8"))
HALF_DAY_THRESHOLD_HOURS = float(os.getenv("HALF_DAY_THRESHOLD_HOURS", "4"))
LATE_ARRIVAL_TIME = os.getenv("LATE_ARRIVAL_TIME", "09:30")  # HH:MM, 24h
