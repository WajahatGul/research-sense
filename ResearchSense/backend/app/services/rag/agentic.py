"""Multi-pass agentic answer pipeline for the ResearchSense RAG chatbot.

Ported from the Pdf_RAG_Chatbot project and adapted to ResearchSense: it runs
over the prebuilt research corpus (researchers, publications, projects, papers)
via the existing retriever, keeps the FastAPI `/api/chat` contract, and calls
Groq over plain HTTP (httpx) — no groq SDK, Django, torch, or faiss required.

Pass architecture:
  Pass 1  — Intent classifier   : what is the user really asking?
  Pass 2  — Evidence extractor  : pull the exact facts from retrieved chunks
  Pass 3  — Answer synthesiser  : write the final, clean, grounded answer

Every Groq call rotates across a CHAIN of high-quality models (each model has
its own daily token budget on the free tier) and across every configured API
key, skipping any (key, model) pair that recently returned 429 until its
rate-limit cooldown expires. When everything is exhausted it degrades to the
fast model, and the caller degrades further to an extractive answer.
"""
from __future__ import annotations

import json
import re
import time
from typing import Dict, List

import httpx

from app.core.config import settings
from app.services.rag.retriever import ScoredChunk

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# The Pass-3 refusal token (matches generator.REFUSAL_TOKEN); when the model
# emits it the caller surfaces the friendly REFUSAL_MESSAGE instead.
REFUSAL_TOKEN = "NO_ANSWER"


# ---------------------------------------------------------------------------
# API keys + model chain
# ---------------------------------------------------------------------------

def _load_groq_keys() -> List[str]:
    """Collect Groq API keys from settings/env. Supports:
      - GROQ_API_KEYS = "key1,key2,key3"   (comma / space / semicolon separated)
      - GROQ_API_KEY, GROQ_API_KEY_2 ... GROQ_API_KEY_9  (single + numbered)
    De-duplicates while preserving order so load rotates across all of them."""
    import os

    keys: List[str] = []
    for part in re.split(r"[,;\s]+", os.getenv("GROQ_API_KEYS", "") or ""):
        if part.strip():
            keys.append(part.strip())
    # settings.groq_api_key already resolves GROQ_API_KEY / GROK_API_KEY.
    if settings.groq_api_key:
        keys.append(settings.groq_api_key)
    for i in range(2, 10):
        val = (os.getenv(f"GROQ_API_KEY_{i}") or "").strip()
        if val:
            keys.append(val)
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


GROQ_API_KEYS = _load_groq_keys()

FAST_MODEL = settings.groq_fast_model
GROQ_MAIN_MODEL_CHAIN = settings.groq_model_chain
# Head of the chain is the default Pass-3 model.
MAIN_MODEL = GROQ_MAIN_MODEL_CHAIN[0] if GROQ_MAIN_MODEL_CHAIN else settings.groq_model

# Per-(key_index, model) cooldown timestamps: stop hammering a bucket that just
# returned 429 until its rate-limit window has likely passed.
_groq_cooldown: Dict[tuple, float] = {}


def available() -> bool:
    """True when at least one Groq key is configured."""
    return bool(GROQ_API_KEYS)


def _retry_after_seconds(msg: str, default: float = 60.0) -> float:
    """Parse 'Please try again in 38m24.288s' / 'in 1.2s' from a 429 body."""
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
    if m:
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return default


# ---------------------------------------------------------------------------
# Low-level Groq caller (multi-key, multi-model failover)
# ---------------------------------------------------------------------------

def _groq_call(
    messages: List[Dict],
    model: str = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    label: str = "",
) -> str:
    """Single logical Groq call with model+key failover. Returns text or ""."""
    if model is None:
        model = MAIN_MODEL
    if not GROQ_API_KEYS:
        return ""

    now = time.time()
    # The fast model is a single-model chain; anything else walks the main chain
    # (an explicit override is honoured at the head) then degrades to fast.
    if model == FAST_MODEL:
        model_chain = [FAST_MODEL]
    else:
        model_chain = list(GROQ_MAIN_MODEL_CHAIN)
        if model not in model_chain:
            model_chain.insert(0, model)
        if FAST_MODEL not in model_chain:
            model_chain.append(FAST_MODEL)

    for attempt, m in enumerate(model_chain):
        for ki, key in enumerate(GROQ_API_KEYS):
            if _groq_cooldown.get((ki, m), 0.0) > now:
                continue
            try:
                resp = httpx.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": m,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": 0.9,
                        "stream": False,
                        # Fixed seed: with temperature 0 this makes repeated
                        # identical requests return the same answer (best-effort;
                        # the API honours it when the backend can).
                        "seed": 42,
                    },
                    timeout=45,
                )
            except httpx.HTTPError as e:
                print(f"  [groq:{label}] HTTP error {m} key#{ki + 1}: {str(e)[:120]}")
                continue

            if resp.status_code == 200:
                try:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, ValueError):
                    continue
                note = f" (model={m}, key#{ki + 1})" if (attempt or ki) else ""
                print(f"  [groq:{label}] {len(text)} chars{note}")
                return text

            body = resp.text
            if resp.status_code == 429 or "rate_limit" in body.lower():
                cd = min(_retry_after_seconds(body), 3600.0)
                _groq_cooldown[(ki, m)] = now + cd
                print(f"  [groq:{label}] RATE-LIMIT {m} key#{ki + 1}; "
                      f"cooldown {cd:.0f}s")
            else:
                print(f"  [groq:{label}] ERROR {resp.status_code} {m} "
                      f"key#{ki + 1}: {body[:120]}")

    return ""


# ---------------------------------------------------------------------------
# Multi-pass agentic pipeline
# ---------------------------------------------------------------------------

def normalize_query(user_message: str,
                    conversation_history: List[Dict]) -> str:
    """Pass 0 — Query understanding (fast model).

    Rewrites a contextual follow-up ("and how?", "is it related to AI?",
    "explain the second one") into a clean, self-contained question by
    resolving pronouns and ellipsis against the recent conversation. Also
    fixes typos and casual abbreviations (u=you, pprs=papers, rsrch=research).

    Ported from Pdf_RAG_Chatbot's _pass0_understand_query. Only runs when
    there IS conversation history to resolve against; returns the message
    unchanged when normalization is unavailable or fails.
    """
    if not GROQ_API_KEYS or not conversation_history:
        return user_message

    snippet = " | ".join(
        f"{m['role']}: {m['content'][:300]}"
        for m in conversation_history[-6:]
    )
    system = (
        "You are a query-understanding module for a university research "
        "assistant chatbot. The user's message may contain typos, casual "
        "abbreviations (u=you, ur=your, pprs/ppr=papers, rsrch/rsearch="
        "research, q=question, info=information), and references to earlier "
        "turns (it/this/that/them/those/'and how'/'why is that'). Use the "
        "recent conversation to resolve those references and rewrite the "
        "message as ONE clean, typo-free, fully self-contained question. "
        "Keep every name, paper title, and topic explicitly. Respond with "
        "ONLY a JSON object — no markdown.\n\n"
        'JSON schema: {"normalized_query": "<self-contained rewrite>"}'
    )
    user_prompt = (
        f"Recent conversation:\n{snippet}\n\n"
        f"User message: {user_message}"
    )
    raw = _groq_call(
        [{"role": "system", "content": system},
         {"role": "user", "content": user_prompt}],
        model=FAST_MODEL,
        temperature=0.0,
        max_tokens=200,
        label="pass0-understand",
    )
    try:
        raw = re.sub(r"```json|```", "", raw).strip()
        norm = (json.loads(raw).get("normalized_query") or "").strip()
        if norm:
            print(f"  [pass0] {user_message!r} -> {norm!r}")
            return norm
    except (ValueError, TypeError):
        pass
    return user_message


def _pass1_classify_intent(user_message: str, conversation_snippet: str) -> Dict:
    """Pass 1 — Intent classification (fast model, tiny prompt)."""
    system = (
        "You are an intent classifier for an academic research assistant chatbot. "
        "Analyse the user message and recent conversation, then respond with ONLY "
        "a valid JSON object — no markdown, no explanation.\n\n"
        "JSON schema:\n"
        '{"intent": "<factual|comparison|summary|methodology|definition|listing|other>",\n'
        ' "focus_entities": ["<key concept or term>"],\n'
        ' "needs_context": <true|false>}'
    )
    user_prompt = (
        f"Recent conversation:\n{conversation_snippet}\n\n"
        f"User message: {user_message}"
    )
    raw = _groq_call(
        [{"role": "system", "content": system},
         {"role": "user", "content": user_prompt}],
        model=FAST_MODEL,
        temperature=0.0,
        max_tokens=150,
        label="pass1-intent",
    )
    try:
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except (ValueError, TypeError):
        return {"intent": "other", "focus_entities": [], "needs_context": False}


def _pass2_extract_evidence(
    user_message: str,
    intent: Dict,
    retrieved_chunks: List[ScoredChunk],
) -> str:
    """Pass 2 — Evidence extraction (fast model)."""
    chunk_block = "\n\n".join(
        f"[Chunk {i + 1} | {c.kind} {c.label} score={c.score:.2f}]\n{c.text}"
        for i, c in enumerate(retrieved_chunks)
    )
    system = (
        "You are an evidence extractor for an academic research assistant. "
        "Your ONLY job is to read the retrieved chunks and extract the facts "
        "that directly answer the question. Be precise and concise.\n\n"
        "Output format (plain text, no markdown headers):\n"
        "RELEVANT_FACTS: <bullet list of exact facts from the chunks>\n"
        "SOURCE_REFS: <list of chunk numbers used, e.g. [1,3]>\n"
        "GAPS: <what the chunks do NOT cover, or 'None'>\n"
        "CONTRADICTIONS: <any conflicting info found, or 'None'>"
    )
    user_prompt = (
        f"User question: {user_message}\n"
        f"Intent: {intent.get('intent', 'other')} | "
        f"Focus: {', '.join(intent.get('focus_entities', []))}\n\n"
        f"Retrieved chunks:\n{chunk_block}"
    )
    return _groq_call(
        [{"role": "system", "content": system},
         {"role": "user", "content": user_prompt}],
        model=FAST_MODEL,
        temperature=0.0,
        max_tokens=800,
        label="pass2-evidence",
    )


def _pass3_synthesise_answer(
    user_message: str,
    intent: Dict,
    evidence_block: str,
    conversation_history: List[Dict],
) -> str:
    """Pass 3 — Answer synthesis (main model chain, high quality)."""
    who = (f"the research assistant of {settings.institution_name}"
           if settings.institution_name
           else "a research assistant for this institution's research portal")
    system = (
        f"You are ResearchSense, {who}. "
        "Write a clear, accurate, well-formatted answer based STRICTLY and "
        "ONLY on the evidence provided below. You have NO knowledge outside the "
        "indexed ResearchSense data (faculty profiles, publications, projects, "
        "and the research papers in the library). Do not invent facts.\n\n"
        "RULES:\n"
        "1. FORMAT: Reply in clean PLAIN TEXT only. Do NOT use Markdown of any "
        "   kind — no asterisks for bold/italics (never write **like this**), no "
        "   '#' headings, no backticks, no tables. The interface shows your reply "
        "   verbatim, so markdown symbols appear as ugly literal characters.\n"
        "2. When listing multiple items, put each on its own line beginning with "
        "   a hyphen and a space ('- '). Keep each line short and scannable. Do "
        "   NOT bold the names.\n"
        "3. Start with one short plain sentence of context, then the list. Do not "
        "   add a trailing summary sentence unless it adds real information.\n"
        "4. Keep the answer concise but complete.\n"
        "5. If the evidence has GAPS, say plainly what you could not find.\n"
        "6. Never invent or modify names, numbers, dates, or titles.\n"
        "7. Maintain a formal, professional tone.\n"
        "8. Do NOT repeat the question back to the user.\n"
        "9. If a context item is marked as a demonstration/sample record, say so "
        "   when using it.\n"
        f"10. STRICT GROUNDING: Answer ONLY from the evidence below. If the answer "
        f"    is not contained there, reply with EXACTLY: {REFUSAL_TOKEN} and stop. "
        "    NEVER use outside or general knowledge, and NEVER answer unrelated "
        "    questions (e.g. trivia, current events) even if you know the answer.\n\n"
        f"INTENT: {intent.get('intent', 'other')}\n\n"
        f"EXTRACTED EVIDENCE:\n{evidence_block}"
    )
    messages = [{"role": "system", "content": system}]
    if intent.get("needs_context"):
        messages.extend(conversation_history[-6:])
    messages.append({"role": "user", "content": user_message})

    return _groq_call(
        messages,
        model=MAIN_MODEL,
        temperature=0.0,
        max_tokens=1500,
        label="pass3-synthesis",
    )


def _strip_markdown(text: str) -> str:
    """Remove markdown decorations the plain-text frontend cannot render, so a
    stray '**bold**' or '### heading' from the model never reaches the user as
    literal symbols. Keeps hyphen bullets and the text content intact."""
    if not text:
        return text
    # Bold/italic: **x** __x__ *x* _x_  ->  x
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    # Inline code `x` -> x
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Leading heading markers and blockquotes at line start
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s{0,3}>\s?", "", text)
    # Normalise markdown bullets (* or +) to a hyphen
    text = re.sub(r"(?m)^(\s*)[*+]\s+", r"\1- ", text)
    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run_agentic_pipeline(
    user_message: str,
    retrieved_chunks: List[ScoredChunk],
    conversation_history: List[Dict],
) -> str:
    """Run the full 3-pass pipeline. Returns the final answer text.

    May return the REFUSAL_TOKEN (caller maps it to the friendly refusal) or ""
    (caller degrades to an extractive answer).
    """
    conversation_snippet = " ".join(
        m["content"] for m in conversation_history[-6:]
    )

    intent = _pass1_classify_intent(user_message, conversation_snippet)
    print(f"  [pipeline] intent={intent}")

    evidence = _pass2_extract_evidence(user_message, intent, retrieved_chunks)
    print(f"  [pipeline] evidence extracted ({len(evidence)} chars)")

    answer = _pass3_synthesise_answer(
        user_message, intent, evidence, conversation_history
    )
    # Keep the refusal token exact for matching; clean everything else so no
    # raw markdown reaches the plain-text frontend.
    if answer and REFUSAL_TOKEN not in answer:
        answer = _strip_markdown(answer)
    return answer
