"""One way to open the SQLite store that always gives the connection back.

``with sqlite3.connect(path) as con:`` looks like it manages the connection,
but sqlite3's context manager only commits or rolls back the transaction —
it never closes. Every account, upload and workspace call therefore leaked a
connection until the garbage collector happened to reap it (100 per test
run). On a busy server that is file handles and memory held for no reason,
and a failure that appears under load rather than in development.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection; commit on success, roll back on error, always close."""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()
