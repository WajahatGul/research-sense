"""Model calls for one answer share a deadline shorter than the browser's.

Without it, failover could walk every key and model with a 45 s timeout
each, long after the visitor's request had been abandoned.
"""

import httpx

from app.services.rag import agentic


class _Ok:
    status_code = 200
    text = ""

    def json(self):
        return {"choices": [{"message": {"content": "an answer"}}]}


def _setup(monkeypatch, calls):
    monkeypatch.setattr(agentic, "GROQ_API_KEYS", ["k1", "k2"])
    monkeypatch.setattr(agentic, "_groq_cooldown", {})

    def fake_post(url, headers, json, timeout):
        calls.append(timeout)
        raise httpx.ReadTimeout("slow provider")

    monkeypatch.setattr(agentic.httpx, "post", fake_post)


def test_no_attempt_starts_once_the_budget_is_spent(monkeypatch):
    calls = []
    _setup(monkeypatch, calls)
    with agentic.answer_deadline(0.5):  # less than the minimum worth trying
        assert agentic._groq_call([{"role": "user", "content": "hi"}]) == ""
    assert calls == []


def test_each_attempt_waits_no_longer_than_the_time_left(monkeypatch):
    calls = []
    _setup(monkeypatch, calls)
    with agentic.answer_deadline(10):
        agentic._groq_call([{"role": "user", "content": "hi"}])
    assert calls, "an attempt should have been made"
    assert all(t <= 10 for t in calls)


def test_without_a_deadline_the_usual_timeout_applies(monkeypatch):
    calls = []
    _setup(monkeypatch, calls)
    agentic._groq_call([{"role": "user", "content": "hi"}])
    assert calls and all(t == 45.0 for t in calls)


def test_a_fast_answer_inside_the_budget_is_returned(monkeypatch):
    monkeypatch.setattr(agentic, "GROQ_API_KEYS", ["k1"])
    monkeypatch.setattr(agentic, "_groq_cooldown", {})
    monkeypatch.setattr(agentic.httpx, "post", lambda *a, **k: _Ok())
    with agentic.answer_deadline():
        assert agentic._groq_call([{"role": "user", "content": "hi"}]) == "an answer"


def test_the_deadline_does_not_leak_past_its_block(monkeypatch):
    with agentic.answer_deadline(5):
        assert agentic._time_left() is not None
    assert agentic._time_left() is None
