"""Loads and caches seed JSON files for the mock repositories.

This is the ONLY place that knows data currently comes from JSON. Swapping to a
real database means writing SQL repositories and leaving this untouched.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def load(name: str) -> list[dict]:
    """Load a seed file (e.g. ``"researchers"``) as a list of dicts.

    Returns an empty list if the file does not exist yet, so the API stays up
    before the scrape script has run.
    """
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def clear_cache() -> None:
    """Drop cached data (used by tests / after re-scraping)."""
    load.cache_clear()
