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

    # Deploying institution's name. ResearchSense is institution-agnostic, but a
    # deployment is always for one university (the customer), so it is set here.
    # This build is configured for Bahria University, which owns the data and
    # campuses shown. A different customer overrides RS_INSTITUTION_NAME (or sets
    # it to "" for a neutral, unbranded look).
    institution_name: str = os.getenv(
        "RS_INSTITUTION_NAME", "Bahria University"
    ).strip()

    # --- RAG chatbot ---
    # Accept both spellings; the key is created at console.groq.com (free tier).
    groq_api_key: str = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY") or ""
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    # Below this cosine similarity the bot refuses instead of answering.
    rag_score_threshold: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.38"))
    # Between the soft threshold and the score threshold the assistant still
    # answers from what it found, but adds a note that its coverage is limited.
    # Below the soft threshold there is nothing meaningfully related, so it
    # gives a helpful redirect instead of guessing.
    rag_soft_threshold: float = float(os.getenv("RAG_SOFT_THRESHOLD", "0.22"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "12"))

    # Weekly in-process data refresh (re-fetch OpenAlex, re-embed the index).
    # Off by default: the index is built locally and committed, and a rebuild
    # of the full Bahria corpus needs far more memory than a small instance
    # has — running it inside the web process would take the site down. Set
    # RS_AUTO_REFRESH=1 only where the box can afford it. The admin endpoint
    # can still trigger a refresh deliberately.
    auto_refresh: bool = os.getenv("RS_AUTO_REFRESH", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    # --- ORCID sign-in (proof of ownership) ---
    # The public registry can only confirm that the NAME on an iD matches the
    # profile being claimed. ORCID iDs are public, so that stops a careless
    # mistake, not someone deliberately claiming a colleague. Signing in at
    # orcid.org proves the iD is actually theirs. Register a free public API
    # client at orcid.org/developer-tools and set these; until then the portal
    # falls back to the name check and says so.
    orcid_client_id: str = os.getenv("ORCID_CLIENT_ID", "").strip()
    orcid_client_secret: str = os.getenv("ORCID_CLIENT_SECRET", "").strip()
    # Must match the redirect URI registered with ORCID exactly.
    orcid_redirect_uri: str = os.getenv(
        "ORCID_REDIRECT_URI", "http://localhost:8000/api/auth/orcid/callback"
    ).strip()
    # Sandbox for development; production issues real iDs.
    orcid_sandbox: bool = os.getenv("ORCID_SANDBOX", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    # Where to send the browser once the round trip is done.
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()

    # --- Developer/test account ---
    # When set, claiming a profile with this exact ORCID iD skips the ORCID
    # registry identity check. For local testing only; leave unset in
    # production.
    dev_orcid: str = os.getenv("DEV_ORCID", "")

    # --- Agentic pipeline (ported from Pdf_RAG_Chatbot) ---
    # Fast model for Pass 0 (query rewrite), Pass 1 (intent) and Pass 2
    # (evidence extraction). Groq retires hosted models on notice and a retired
    # one 404s silently, so this must be one the deployment's keys can actually
    # call — verify with a probe before changing it. The previous default
    # (llama-3.1-8b-instant) is gone. Note gpt-oss is a reasoning model: its
    # reasoning tokens count against max_tokens, which is why those passes get
    # a wider budget than their JSON replies need.
    groq_fast_model: str = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
    # Pass 3 (synthesis) walks this chain of high-quality models: each Groq
    # model has its own daily token budget, so a rate-limited model rolls to the
    # next full bucket before finally degrading to the fast model. Every entry
    # must be a model the keys can call; the chain previously listed three that
    # Groq no longer serves, leaving only the head doing any work. Env override:
    # GROQ_MODEL_CHAIN="model-a,model-b,...".
    groq_model_chain: list[str] = [
        m.strip()
        for m in os.getenv(
            "GROQ_MODEL_CHAIN",
            "openai/gpt-oss-120b,openai/gpt-oss-20b",
        ).split(",")
        if m.strip()
    ]


settings = Settings()
