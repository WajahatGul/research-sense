"""Which institution the request being served belongs to.

The deployment's configured name (``RS_INSTITUTION_NAME``) brands the bundled
demo corpus. An institution that signed up for its own workspace is branded
with the name it registered, so its profiles and its assistant say *its* name
rather than the demo's.
"""

from __future__ import annotations

from app.core.config import settings
from app.repositories import loader

# An institution's name is fixed at sign-up, so one lookup per workspace is
# enough — this keeps the per-response validator off the database.
_names: dict[str, str] = {}


def institution_name(workspace: str | None = None) -> str:
    """The institution to brand the given (or current) workspace with."""
    ws = workspace or loader.current_workspace()
    if ws == loader.DEFAULT_WORKSPACE:
        return settings.institution_name
    if ws not in _names:
        # Imported here: the workspace store opens the SQLite database, and
        # nothing should pay for that until a workspace request arrives.
        from app.repositories.workspaces import WorkspaceStore

        row = WorkspaceStore.instance().workspace(ws) or {}
        _names[ws] = row.get("institution_name") or ""
    return _names[ws]


def forget(workspace: str | None = None) -> None:
    """Drop cached names (used by tests and after a workspace is created)."""
    if workspace is None:
        _names.clear()
    else:
        _names.pop(workspace, None)
