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

    # Deploying institution's name. ResearchSense is institution-agnostic: leave
    # this empty for the neutral product-only look, or set RS_INSTITUTION_NAME
    # (e.g. "Meridian University") to brand every answer and index entry for one
    # institution.
    institution_name: str = os.getenv("RS_INSTITUTION_NAME", "").strip()

    # --- RAG chatbot ---
    # Accept both spellings; the key is created at console.groq.com (free tier).
    groq_api_key: str = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or ""
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    # Below this cosine similarity the bot refuses instead of answering.
    rag_score_threshold: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.38"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "12"))

    # --- Developer/test account ---
    # When set, claiming a profile with this exact ORCID iD skips the ORCID
    # registry identity check. For local testing only; leave unset in
    # production.
    dev_orcid: str = os.getenv("DEV_ORCID", "")

    # --- Agentic pipeline (ported from Pdf_RAG_Chatbot) ---
    # Fast model for Pass 1 (intent) and Pass 2 (evidence extraction).
    groq_fast_model: str = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
    # Pass 3 (synthesis) walks this chain of high-quality models: each Groq
    # model has its own daily token budget, so a rate-limited model rolls to the
    # next full bucket before finally degrading to the fast model. Env override:
    # GROQ_MODEL_CHAIN="model-a,model-b,...".
    groq_model_chain: list[str] = [
        m.strip() for m in os.getenv(
            "GROQ_MODEL_CHAIN",
            "openai/gpt-oss-120b,"
            "llama-3.3-70b-versatile,"
            "qwen/qwen3-32b,"
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ).split(",") if m.strip()
    ]


settings = Settings()
