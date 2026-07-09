"""Application configuration."""
from __future__ import annotations

import os


class Settings:
    """Runtime settings, overridable via environment variables."""

    app_name: str = "ResearchSense API"
    version: str = "0.1.0"
    # Comma-separated list of allowed CORS origins (Vite dev server by default).
    cors_origins: list[str] = os.getenv(
        "RS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")


settings = Settings()
