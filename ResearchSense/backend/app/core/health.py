"""Health that describes what users would experience, not whether the
process is running.

The old check returned "ok" unconditionally, so a deploy whose research
corpus failed to load passed Render's health check and replaced a working
version. The corpus is the product: without it every page is empty, so its
absence is a hard failure (HTTP 503 keeps the old version live). The
assistant's index is one feature among many: its absence is reported as
degraded, but does not take the directory and publications down with it.
"""

from __future__ import annotations

from app.repositories import loader


def check() -> tuple[bool, dict]:
    """Return (serving, report). ``serving`` is False only when users would
    see an empty site."""
    report: dict = {}

    try:
        people = sum(1 for r in loader.load("researchers") if not loader.is_extended(r))
        papers = len(loader.load("publications"))
        report["corpus"] = {
            "ok": people > 0 and papers > 0,
            "researchers": people,
            "publications": papers,
        }
    except Exception as exc:  # a corrupt or missing file must not 500 the probe
        report["corpus"] = {"ok": False, "error": type(exc).__name__}

    data = loader.DATA_DIR
    report["assistant_index"] = {
        "ok": (data / "rag_index.npz").is_file()
        and (data / "rag_chunks.json").is_file()
    }

    serving = report["corpus"]["ok"]
    if not serving:
        report["status"] = "down"
    elif not report["assistant_index"]["ok"]:
        report["status"] = "degraded"
    else:
        report["status"] = "ok"
    return serving, report
