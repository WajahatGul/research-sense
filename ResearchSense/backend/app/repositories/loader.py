"""Loads and caches seed JSON files for the mock repositories.

This is the ONLY place that knows data currently comes from JSON. Swapping to a
real database means writing SQL repositories and leaving this untouched.

Data is scoped to a **workspace** (an institution's own space). The default
workspace is the bundled corpus that the public demo serves; a workspace created
by a signed-up institution keeps its own files under ``data/workspaces/<id>/``.
The active workspace travels in a context variable set once per request, so
repositories keep calling ``load("researchers")`` and stay unaware of tenancy.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WORKSPACES_DIR = DATA_DIR / "workspaces"

#: The bundled corpus (the public demo). Its files stay at the top of ``data/``.
DEFAULT_WORKSPACE = "demo"

_current_workspace: ContextVar[str] = ContextVar(
    "current_workspace", default=DEFAULT_WORKSPACE
)


def set_workspace(workspace: str | None) -> None:
    """Set the workspace for the current request (falls back to the demo)."""
    _current_workspace.set(workspace or DEFAULT_WORKSPACE)


def current_workspace() -> str:
    return _current_workspace.get()


def workspace_dir(workspace: str) -> Path:
    """Where a workspace's JSON files live."""
    if workspace == DEFAULT_WORKSPACE:
        return DATA_DIR
    return WORKSPACES_DIR / workspace


@cache
def _load(name: str, workspace: str) -> list[dict]:
    path = workspace_dir(workspace) / f"{name}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load(name: str) -> list[dict]:
    """Load a seed file (e.g. ``"researchers"``) for the active workspace.

    Returns an empty list if the file does not exist yet, so the API stays up
    before the scrape script has run and while a new workspace is still empty.
    """
    return _load(name, current_workspace())


def save(name: str, rows: list[dict], workspace: str) -> None:
    """Write a workspace's file and drop the cached copy so reads see it."""
    directory = workspace_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
    clear_cache()


def clear_cache() -> None:
    """Drop cached data (used by tests / after re-scraping or a write)."""
    _load.cache_clear()
