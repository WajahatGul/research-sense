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
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from collections.abc import Iterable, Mapping

_TOKEN = re.compile(r"[a-z0-9]+")
# Long enough that matching inside a compacted phrase is meaningful rather
# than accidental ("ai" occurs inside hundreds of unrelated words).
_MIN_COMPACT_TERM = 5
_MIN_VOCAB_WORD = 3


def _singular(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def tokens(text: str | None) -> list[str]:
    """Lower-cased, singularised word tokens of ``text``."""
    return [_singular(t) for t in _TOKEN.findall((text or "").lower())]


class Query:
    """A parsed search query that can match and rank records."""

    def __init__(self, text: str | None):
        self.text = (text or "").strip()
        self.terms = tokens(self.text)

    def __bool__(self) -> bool:
        return bool(self.terms)

    def matches(self, *fields: str | None) -> bool:
        """Every term appears somewhere across ``fields``, in any order."""
        words = [w for f in fields for w in tokens(f)]
        compact = "".join(words)
        return all(
            any(w.startswith(t) for w in words)
            or (len(t) >= _MIN_COMPACT_TERM and t in compact)
            for t in self.terms
        )

    def score(self, primary: str | None, *secondary: str | None) -> float | None:
        """Relevance of a record, or None when it does not match.

        ``primary`` is the field people usually mean (a name, a title).
        An exact or leading match there outranks a match buried in a
        secondary field, so the person you typed comes first.
        """
        if not self.matches(primary, *secondary):
            return None
        head = tokens(primary)
        phrase = " ".join(self.terms)
        joined = " ".join(head)
        score = 0.0
        if joined == phrase:
            score += 100
        elif joined.startswith(phrase):
            score += 60
        elif phrase in joined:
            score += 40
        score += 20 * sum(1 for t in self.terms if any(w.startswith(t) for w in head))
        return score


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
