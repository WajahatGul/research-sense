"""Uvicorn entrypoint: ``uvicorn app.main:app --reload``."""
from __future__ import annotations

from app.core.app import create_app

app = create_app()
