"""Model failover in the agentic pipeline.

Groq retires hosted models on notice. A retired one answers 404 for every key
and never recovers, and the passes pinned to the fast model then return nothing
— which drops the evidence block and turns every answer into a refusal. That is
exactly how the assistant broke in production, so the handling is pinned here.
"""

from __future__ import annotations

import pytest

from app.services.rag import agentic


class _Resp:
    def __init__(self, status_code: int, text: str, content: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self._content = content

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


# Groq's real wordings for the two ways a model goes away, and for a
# rate limit (which must NOT be mistaken for one).
RETIRED = (
    '{"error":{"message":"The model `x` does not exist or you do not'
    ' have access to it."}}'
)
DECOMMISSIONED = (
    '{"error":{"message":"The model `x` has been decommissioned and is'
    ' no longer supported."}}'
)
RATE_LIMITED = '{"error":{"message":"rate_limit_exceeded","type":"tokens"}}'


@pytest.fixture(autouse=True)
def clean_failover_state(monkeypatch):
    monkeypatch.setattr(agentic, "GROQ_API_KEYS", ["key-one", "key-two"])
    agentic._dead_models.clear()
    agentic._groq_cooldown.clear()
    yield
    agentic._dead_models.clear()
    agentic._groq_cooldown.clear()


def _record_calls(monkeypatch, responder):
    """Install a fake transport and return the list of models it was asked for."""
    asked: list[str] = []

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        asked.append(json["model"])
        return responder(json["model"])

    monkeypatch.setattr(agentic.httpx, "post", fake_post)
    return asked


def test_retired_fast_model_falls_back_instead_of_returning_nothing(monkeypatch):
    def responder(model: str):
        if model == agentic.FAST_MODEL:
            return _Resp(404, RETIRED)
        return _Resp(200, "", "the answer")

    asked = _record_calls(monkeypatch, responder)
    out = agentic._groq_call(
        [{"role": "user", "content": "hi"}], model=agentic.FAST_MODEL
    )

    assert out == "the answer"
    assert agentic.FAST_MODEL in agentic._dead_models
    # Asked once, not once per key: every key gets the same 404.
    assert asked.count(agentic.FAST_MODEL) == 1


def test_a_dead_model_is_not_tried_again(monkeypatch):
    agentic._dead_models.add(agentic.FAST_MODEL)

    asked = _record_calls(monkeypatch, lambda _m: _Resp(200, "", "ok"))
    assert (
        agentic._groq_call(
            [{"role": "user", "content": "hi"}], model=agentic.FAST_MODEL
        )
        == "ok"
    )
    assert agentic.FAST_MODEL not in asked


def test_a_decommissioned_model_counts_as_retired(monkeypatch):
    def responder(model: str):
        if model == agentic.MAIN_MODEL:
            return _Resp(400, DECOMMISSIONED)
        return _Resp(200, "", "fallback answer")

    _record_calls(monkeypatch, responder)
    out = agentic._groq_call(
        [{"role": "user", "content": "hi"}], model=agentic.MAIN_MODEL
    )

    assert out == "fallback answer"
    assert agentic.MAIN_MODEL in agentic._dead_models


def test_a_rate_limited_model_is_never_marked_dead(monkeypatch):
    """It recovers when the budget resets — poisoning it would be permanent."""
    _record_calls(monkeypatch, lambda _m: _Resp(429, RATE_LIMITED))
    assert agentic._groq_call([{"role": "user", "content": "hi"}]) == ""
    assert agentic._dead_models == set()
