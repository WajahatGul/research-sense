"""A model outage must never be reported as missing data.

Observed in the running product: the same question answered "I could not find
anything on that in the records I have indexed so far", then answered fully a
few minutes later. Nothing about the data changed — the fast model behind the
evidence-extraction pass was rate-limited, so Pass 3 received an empty evidence
block, correctly refused, and the refusal surfaced as a claim about the corpus.

The distinction matters: "we have no record of that" is a factual statement
about the institution's research. It must never be produced by a temporary
infrastructure failure.
"""

from __future__ import annotations

from app.services.rag import agentic
from app.services.rag.retriever import ScoredChunk

CHUNKS = [
    ScoredChunk(
        text=(
            "Highly accurate protein structure prediction with AlphaFold "
            "presents AlphaFold2, a deep-learning system for protein folding."
        ),
        kind="paper",
        ref_id=None,
        label="Library: Highly accurate protein structure prediction",
        score=0.71,
    ),
    ScoredChunk(
        text="Nida Aman is an Associate Professor in Accounting and Finance.",
        kind="researcher",
        ref_id=1,
        label="Nida Aman — Associate Professor",
        score=0.40,
    ),
]


def test_a_rate_limited_extraction_pass_still_reaches_the_answer(monkeypatch):
    """Pass 2 returning nothing must not empty the evidence handed to Pass 3."""
    seen: list[str] = []
    pass3_evidence: list[str] = []

    def fake_call(messages, model=None, temperature=0.2, max_tokens=1024, label=""):
        seen.append(label)
        if label == "pass3-synthesis":
            pass3_evidence.append(" ".join(m["content"] for m in messages))
            return "AlphaFold2 predicts protein structures."
        return ""  # pass 1 and pass 2 are rate-limited

    monkeypatch.setattr(agentic, "_groq_call", fake_call)

    answer = agentic.run_agentic_pipeline(
        user_message="Summarize the AlphaFold paper",
        retrieved_chunks=CHUNKS,
        conversation_history=[],
    )

    assert "pass3-synthesis" in seen
    assert answer and agentic.REFUSAL_TOKEN not in answer
    # Pass 3 saw the retrieved text rather than an empty block.
    assert "AlphaFold2" in pass3_evidence[0]
    assert "RELEVANT_FACTS" in pass3_evidence[0]


def test_the_fallback_carries_the_retrieved_records():
    block = agentic._raw_evidence(CHUNKS)
    assert "AlphaFold2" in block
    assert "Nida Aman" in block
    assert block.startswith("RELEVANT_FACTS")


def test_nothing_retrieved_still_yields_nothing():
    """With no chunks there is genuinely no evidence — refusing is correct."""
    assert agentic._raw_evidence([]) == ""


def test_a_genuine_refusal_is_left_alone(monkeypatch):
    """When the model reads real evidence and says no, that answer stands."""

    def fake_call(messages, model=None, temperature=0.2, max_tokens=1024, label=""):
        if label == "pass3-synthesis":
            return agentic.REFUSAL_TOKEN
        return "RELEVANT_FACTS: none of the chunks mention this."

    monkeypatch.setattr(agentic, "_groq_call", fake_call)

    answer = agentic.run_agentic_pipeline(
        user_message="What is the capital of France?",
        retrieved_chunks=CHUNKS,
        conversation_history=[],
    )
    assert agentic.REFUSAL_TOKEN in answer
