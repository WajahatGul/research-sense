"""Application configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env so secrets stay out of the repo.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    """Runtime settings, overridable via environment variables."""

    app_name: str = "ResearchSense API"
    version: str = "0.1.0"
    # Comma-separated list of allowed CORS origins (Vite dev server by default).
    cors_origins: list[str] = os.getenv(
        "RS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")

    # --- RAG chatbot ---
    # Accept both spellings; the key is created at console.groq.com (free tier).
    groq_api_key: str = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or ""
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    # Below this cosine similarity the bot refuses instead of answering.
    rag_score_threshold: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.38"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "12"))


settings = Settings()
