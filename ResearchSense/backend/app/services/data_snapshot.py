"""Keep the served data whole through a refresh.

The refresh runs several scripts that each rewrite files in the data folder
in place: the fetch, the clean-ups, the area filing, the index rebuild. One
failing halfway (a network error, a crash, running out of memory) left some
files new and some old: publications renumbered but the logs that name them
by number deleted, or the index out of step with its chunks. Nothing
noticed; the site kept serving the mixture.

Now the refresh copies every file it can touch before it starts, checks the
result when it finishes, and puts the copy back if anything failed or the
check does not pass. The check asks what a user would notice: that the data
loads, that it has not suddenly lost most of its people or papers, that
paper numbers are unique, and that the assistant's index is consistent.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

#: Everything a refresh may rewrite.
FILES = (
    "researchers.json", "publications.json", "topics.json",
    "rag_chunks.json", "rag_index.npz",
    "author_merges.json", "author_unlinks.json", "publication_duplicates.json",
)
SNAPSHOT_DIR = ".refresh-snapshot"
# A real refresh adds and removes a little; losing more than this is a fault.
MIN_KEPT_RESEARCHERS = 0.9
MIN_KEPT_PUBLICATIONS = 0.8


class DataCheckFailed(RuntimeError):
    """The refreshed data is not fit to serve."""


def _counts(data_dir: Path) -> dict:
    def load(name):
        path = data_dir / f"{name}.json"
        return json.loads(path.read_text("utf-8")) if path.exists() else []

    researchers = [r for r in load("researchers") if r.get("source") != "openalex"]
    return {"researchers": len(researchers), "publications": len(load("publications"))}


def take(data_dir: Path) -> dict:
    """Copy every file a refresh may rewrite; return the counts before it."""
    snap = data_dir / SNAPSHOT_DIR
    shutil.rmtree(snap, ignore_errors=True)
    snap.mkdir(parents=True)
    for name in FILES:
        if (data_dir / name).exists():
            shutil.copy2(data_dir / name, snap / name)
    (snap / "present.json").write_text(
        json.dumps([n for n in FILES if (data_dir / n).exists()]), "utf-8"
    )
    return _counts(data_dir)


def restore(data_dir: Path) -> None:
    """Put the pre-refresh files back exactly, including ones it deleted."""
    snap = data_dir / SNAPSHOT_DIR
    present = set(json.loads((snap / "present.json").read_text("utf-8")))
    for name in FILES:
        if name in present:
            shutil.copy2(snap / name, data_dir / name)
        else:
            (data_dir / name).unlink(missing_ok=True)


def discard(data_dir: Path) -> None:
    shutil.rmtree(data_dir / SNAPSHOT_DIR, ignore_errors=True)


def check(data_dir: Path, before: dict) -> None:
    """Raise DataCheckFailed unless the refreshed data is fit to serve."""
    try:
        after = _counts(data_dir)
        publications = json.loads((data_dir / "publications.json").read_text("utf-8"))
        topics = json.loads((data_dir / "topics.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise DataCheckFailed(f"the data does not load ({exc})") from exc
    if after["researchers"] < MIN_KEPT_RESEARCHERS * before["researchers"]:
        raise DataCheckFailed(
            f"directory shrank from {before['researchers']} to {after['researchers']} people"
        )
    if after["publications"] < MIN_KEPT_PUBLICATIONS * before["publications"]:
        raise DataCheckFailed(
            f"papers fell from {before['publications']} to {after['publications']}"
        )
    ids = [p.get("publication_id") for p in publications]
    if len(ids) != len(set(ids)) or None in ids:
        raise DataCheckFailed("paper numbers are missing or repeated")
    if not topics:
        raise DataCheckFailed("there are no research areas")
    chunks_path, index_path = data_dir / "rag_chunks.json", data_dir / "rag_index.npz"
    if chunks_path.exists() and index_path.exists():
        chunks = json.loads(chunks_path.read_text("utf-8"))
        vectors = np.load(index_path)["vectors"]
        if len(chunks) != len(vectors):
            raise DataCheckFailed(
                f"the assistant's index has {len(vectors)} vectors for {len(chunks)} passages"
            )
