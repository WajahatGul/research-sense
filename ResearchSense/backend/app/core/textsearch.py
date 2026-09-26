"""Forgiving text search shared by the directory, publications and areas.

People type queries with the words in any order ("naseer kashif"), in the
plural ("smart cities"), with or without a space ("cyber security" vs
"cybersecurity"), and with typos ("machin lerning"). A literal substring
check fails every one of those and answers "no results" for data we hold,
which reads as "this site has nothing" rather than "I mistyped".

Matching works on normalised tokens: a query term matches when it starts a
word in the record, or (for longer terms) appears anywhere once spaces are
removed. When a query finds nothing, ``correct`` proposes the closest words
from the corpus so the caller can show "Showing results for …".

Records are tokenised once per loaded dataset (``index_for``) rather than on
every query: re-tokenising 9,500 publications per keystroke-sized request
cost ~0.4 s on a hit and ~1.4 s on a typo.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence

_TOKEN = re.compile(r"[a-z0-9]+")
# Long enough that matching inside a compacted phrase is meaningful rather
# than accidental ("ai" occurs inside hundreds of unrelated words).
_MIN_COMPACT_TERM = 5
_MIN_VOCAB_WORD = 3
# Datasets indexed at once (demo corpus plus a few institution workspaces).
_MAX_INDEXES = 8


def _singular(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def tokens(text: str | None) -> list[str]:
    """Lower-cased, singularised word tokens of ``text``."""
    return [_singular(t) for t in _TOKEN.findall((text or "").lower())]


class Entry:
    """One record's searchable text, prepared for fast matching.

    ``spaced`` is " w1 w2 …": a term starts a word exactly when " term"
    occurs in it, so prefix matching becomes one substring test.
    """

    __slots__ = ("head", "head_spaced", "spaced", "compact")

    def __init__(self, primary: str | None, *secondary: str | None):
        head = tokens(primary)
        words = head + [w for f in secondary for w in tokens(f)]
        self.head = " ".join(head)
        self.head_spaced = " " + self.head
        self.spaced = " " + " ".join(words)
        self.compact = "".join(words)


class Query:
    """A parsed search query that can match and rank records."""

    def __init__(self, text: str | None):
        self.text = (text or "").strip()
        self.terms = tokens(self.text)
        self._phrase = " ".join(self.terms)

    def __bool__(self) -> bool:
        return bool(self.terms)

    def score_entry(self, e: Entry) -> float | None:
        """Relevance of a prepared record, or None when it does not match.

        Every term must appear (any order). An exact or leading match in the
        primary field (a name, a title) outranks one buried elsewhere, so the
        person you typed comes first.
        """
        for t in self.terms:
            if f" {t}" not in e.spaced and not (
                len(t) >= _MIN_COMPACT_TERM and t in e.compact
            ):
                return None
        score = 0.0
        if e.head == self._phrase:
            score += 100
        elif e.head.startswith(self._phrase):
            score += 60
        elif self._phrase in e.head:
            score += 40
        score += 20 * sum(1 for t in self.terms if f" {t}" in e.head_spaced)
        return score

    def score(self, primary: str | None, *secondary: str | None) -> float | None:
        return self.score_entry(Entry(primary, *secondary))

    def matches(self, *fields: str | None) -> bool:
        """Every term appears somewhere across ``fields``, in any order."""
        return self.score(*fields) is not None


def vocabulary(texts: Iterable[str | None]) -> Counter[str]:
    """Corpus word frequencies, used to rank spelling corrections."""
    return Counter(
        t for text in texts for t in tokens(text) if len(t) >= _MIN_VOCAB_WORD
    )


def correct(text: str | None, vocab: Mapping[str, int]) -> str | None:
    """Closest in-corpus spelling of ``text``, or None if nothing changes.

    Among the near spellings, the word the corpus uses most wins: real data
    contains its own typos ("leraning"), and a rare misspelling must not
    beat the common word the visitor obviously meant.
    """
    out: list[str] = []
    changed = False
    for term in tokens(text):
        if term in vocab or len(term) < _MIN_VOCAB_WORD:
            out.append(term)
            continue
        near = difflib.get_close_matches(term, vocab.keys(), n=5, cutoff=0.75)
        if near:
            out.append(max(near, key=lambda w: vocab[w]))
            changed = True
        else:
            out.append(term)
    return " ".join(out) if changed else None


class SearchIndex:
    """Prepared entries and word frequencies for one loaded dataset."""

    def __init__(
        self, rows: Sequence[dict], fields: Callable[[dict], Sequence[str | None]]
    ):
        self.rows = rows  # held so the dataset's identity cannot be reused
        self.entries = [Entry(*fields(r)) for r in rows]
        self._fields = fields
        self._vocab: Counter[str] | None = None

    @property
    def vocab(self) -> Counter[str]:
        # Built on the first miss only; most queries never need it.
        if self._vocab is None:
            self._vocab = vocabulary(f for r in self.rows for f in self._fields(r))
        return self._vocab


_indexes: OrderedDict[tuple[str, int], SearchIndex] = OrderedDict()


def index_for(
    name: str, rows: Sequence[dict], fields: Callable[[dict], Sequence[str | None]]
) -> SearchIndex:
    """The index for this exact dataset object, built on first use.

    The loader returns the same list until data is refreshed, and a new list
    afterwards, so identity is a correct and free invalidation signal.
    """
    key = (name, id(rows))
    idx = _indexes.get(key)
    if idx is None or idx.rows is not rows:
        idx = SearchIndex(rows, fields)
        _indexes[key] = idx
        while len(_indexes) > _MAX_INDEXES:
            _indexes.popitem(last=False)
    else:
        _indexes.move_to_end(key)
    return idx
