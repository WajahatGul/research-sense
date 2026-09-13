"""Guards that keep a full rebuild from taking the deployed site down.

The Bahria import grew the index from ~3k chunks to ~21k. Embedding that in
one call peaked near 1.6 GB, and the weekly refresh runs inside the web
process — so on a small instance the refresh would OOM the whole service.
"""

from __future__ import annotations

import asyncio

import numpy as np

from app.core.config import settings
from app.services import refresh_service


class _StubModel:
    """Stands in for fastembed: records the batch sizes it was handed."""

    def __init__(self) -> None:
        self.batches: list[int] = []

    def embed(self, texts):
        texts = list(texts)
        self.batches.append(len(texts))
        # Distinct, non-unit vectors so normalisation is observable.
        for i, _t in enumerate(texts, start=1):
            yield np.full(384, float(i), dtype=np.float32)


def test_embedding_is_fed_in_bounded_batches():
    from scripts.build_index import EMBED_BATCH, embed_all

    model = _StubModel()
    out = embed_all([f"chunk {i}" for i in range(EMBED_BATCH + 10)], model)

    assert out.shape == (EMBED_BATCH + 10, 384)
    assert max(model.batches) <= EMBED_BATCH, "a batch exceeded the cap"
    assert sum(model.batches) == EMBED_BATCH + 10


def test_embeddings_come_back_normalised():
    """Cosine similarity is a plain dot product at query time, so it must be."""
    from scripts.build_index import embed_all

    out = embed_all([f"chunk {i}" for i in range(5)], _StubModel())
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_embedding_nothing_is_not_an_error():
    from scripts.build_index import embed_all

    assert embed_all([], _StubModel()).shape == (0, 384)


def test_the_weekly_refresh_stays_off_unless_asked_for(monkeypatch):
    """It must not start on its own: a rebuild would exhaust a small instance."""
    monkeypatch.setattr(settings, "auto_refresh", False)
    called = False

    def _boom():
        nonlocal called
        called = True

    monkeypatch.setattr(refresh_service, "is_due", _boom)
    # Returns immediately instead of entering the daily loop; asyncio.wait_for
    # would hang here if the guard were missing.
    asyncio.run(asyncio.wait_for(refresh_service.weekly_refresh_loop(), timeout=5))
    assert called is False
