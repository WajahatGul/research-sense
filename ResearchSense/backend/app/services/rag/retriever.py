"""Semantic retriever for the RAG chatbot.

Loads the prebuilt index (rag_chunks.json + rag_index.npz), embeds the user's
question locally with all-MiniLM-L6-v2, and returns the top-k chunks with
cosine scores. The confidence gate lives here: if nothing scores above the
threshold, the caller must refuse instead of answering.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Persistent model cache (the OS temp folder gets cleaned).
MODEL_CACHE = Path(__file__).resolve().parents[3] / ".fastembed_cache"


# Common transliteration variants in Pakistani names, applied per token so
# "Arif ur Rehman" in a question matches "Arif Ur Rahman" in the data.
_NAME_VARIANTS = {
    "rehman": "rahman", "rahmaan": "rahman",
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad",
    "muhammd": "muhammad", "mohd": "muhammad",
    "syed": "syed", "sayed": "syed", "sayyed": "syed",
    "hussain": "hussain", "husain": "hussain", "hussein": "hussain",
    "usman": "usman", "othman": "usman", "uthman": "usman",
    "fatima": "fatima", "fatimah": "fatima",
    "ali": "ali", "aly": "ali",
}


def _norm_name(text: str) -> str:
    """Normalize a name (or question) for variant-tolerant containment."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return "".join(_NAME_VARIANTS.get(t, t) for t in tokens)


@dataclass
class ScoredChunk:
    text: str
    kind: str
    ref_id: int | None
    label: str
    score: float


class Retriever:
    """Lazy singleton over the embedding model and the vector index."""

    _instance: "Retriever | None" = None

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # deferred: slow import

        self._model = TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))
        self._chunks: list[dict] = json.loads(
            (DATA_DIR / "rag_chunks.json").read_text("utf-8"))
        self._vectors: np.ndarray = np.load(DATA_DIR / "rag_index.npz")["vectors"]
        self._lowered: list[str] = [c["text"].lower() for c in self._chunks]
        # Known researcher names (without titles) for entity-aware boosting.
        # Stored both raw (for chunk matching) and normalized (for matching
        # transliteration variants in the question, e.g. Rehman vs Rahman).
        raw_names = sorted({
            re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s+", "",
                   c["label"].split(" — ")[0].strip().lower())
            for c in self._chunks if c["kind"] == "researcher"
        })
        self._names: list[tuple[str, str]] = [
            (name, _norm_name(name)) for name in raw_names
        ]

    @classmethod
    def instance(cls) -> "Retriever":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def available(cls) -> bool:
        return ((DATA_DIR / "rag_chunks.json").exists()
                and (DATA_DIR / "rag_index.npz").exists())

    @classmethod
    def reset(cls) -> None:
        """Drop the cached instance so the next query reloads the index."""
        cls._instance = None

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        """Hybrid ranking: cosine similarity + a lexical bonus.

        Pure embeddings miss questions keyed on names and years ("what did X
        publish in 2022"), because the matching chunks are about the paper's
        topic, not the question's wording. Distinctive query tokens found
        verbatim in a chunk add a small bonus so those chunks surface.
        """
        k = k or settings.rag_top_k
        q = np.array(list(self._model.embed([query]))[0], dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = (self._vectors @ q
                  + self._lexical_bonus(query)
                  + self._entity_bonus(query))
        top = np.argsort(scores)[::-1][:k]
        return [
            ScoredChunk(
                text=self._chunks[i]["text"],
                kind=self._chunks[i]["kind"],
                ref_id=self._chunks[i]["ref_id"],
                label=self._chunks[i]["label"],
                score=float(scores[i]),
            )
            for i in top
        ]

    _STOPWORDS = {
        "what", "when", "where", "which", "whose", "about", "does", "did",
        "have", "has", "the", "and", "for", "with", "from", "who", "how",
        "publish", "published", "research", "work", "works", "tell",
        "campus", "university", "bahria", "professor", "doctor", "papers",
        "paper", "publication", "publications",
    }

    def _lexical_bonus(self, query: str) -> np.ndarray:
        tokens = {
            t for t in re.findall(r"[a-z0-9]+", query.lower())
            if (len(t) >= 4 and t not in self._STOPWORDS) or re.fullmatch(r"(19|20)\d{2}", t)
        }
        bonus = np.zeros(len(self._chunks), dtype=np.float32)
        if not tokens:
            return bonus
        for i, lowered in enumerate(self._lowered):
            hits = sum(1 for t in tokens if t in lowered)
            if hits:
                bonus[i] = min(0.07 * hits, 0.28)
        return bonus

    def _entity_bonus(self, query: str) -> np.ndarray:
        """Decisive boost for chunks about a researcher named in the question.

        "What did X publish in 2022?" is an entity lookup, not a semantic
        match: the correct publication chunks share almost no wording with the
        question. When the question contains a known researcher's exact name,
        every chunk mentioning that name is boosted; if the question also
        names a year, chunks with both name and year are boosted further.
        """
        normalized_query = _norm_name(query)
        named = [raw for raw, norm in self._names if norm in normalized_query]
        bonus = np.zeros(len(self._chunks), dtype=np.float32)
        if not named:
            return bonus
        years = set(re.findall(r"(?:19|20)\d{2}", query))
        for i, text in enumerate(self._lowered):
            if any(n in text for n in named):
                bonus[i] = 0.35
                if years and any(y in text for y in years):
                    bonus[i] = 0.5
        return bonus


def is_confident(results: list[ScoredChunk]) -> bool:
    """True when retrieval found something actually relevant."""
    return bool(results) and results[0].score >= settings.rag_score_threshold
