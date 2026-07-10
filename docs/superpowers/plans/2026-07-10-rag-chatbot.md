# RAG Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grounded RAG chatbot over ResearchSense data + real papers of Dr. Arif ur Rahman, with hard anti-hallucination gates and zero running cost.

**Architecture:** download_papers → build_index (fastembed MiniLM, numpy store) → retriever (gate) → generator (Groq strict prompt | extractive fallback) → chat_service. Spec: `docs/superpowers/specs/2026-07-10-rag-chatbot-design.md`.

**Tech Stack:** fastembed, numpy, pypdf, python-dotenv, httpx, Groq REST (llama-3.3-70b-versatile, temp 0).

## Global Constraints
- Files ≤ 350 lines; routers thin; data access stays behind existing seams.
- LLM may only see retrieved context; sources returned from retrieval only.
- `.env` never committed (already git-ignored). PDFs live in `backend/papers/`.

### Task 1: Dependencies + env loading
- [ ] Add fastembed, pypdf, python-dotenv to requirements.txt and install.
- [ ] `core/config.py`: load `.env`, expose `groq_api_key`, `groq_model`, `rag_score_threshold`.

### Task 2: download_papers.py
- [ ] Resolve Dr. Arif ur Rahman's OpenAlex author id (Bahria-affiliated), list works with `best_oa_location.pdf_url`, download up to 20 PDFs to `backend/papers/`, write `manifest.json` (title, year, doi, filename). Verify ≥10 PDFs readable by pypdf.

### Task 3: build_index.py
- [ ] Chunks from researchers/publications/projects/topics JSONs (one fact-card each) + PDF text chunks (~800 chars, 150 overlap, per-paper metadata).
- [ ] Embed all with fastembed all-MiniLM-L6-v2; save `app/data/rag_chunks.json` + `rag_index.npz`. Print counts.

### Task 4: retriever + generator
- [ ] `services/rag/retriever.py`: lazy singleton (chunks, matrix, model); `retrieve(query, k=8)` → scored chunks; `is_confident(scores)` gate.
- [ ] `services/rag/generator.py`: `generate(question, chunks)` → Groq REST (temp 0, strict system prompt, `NO_ANSWER` token) with try/except → `extractive(chunks)` fallback; returns (answer, used_llm).

### Task 5: chat_service rewrite + wiring
- [ ] Rewrite `chat_service.py`: retrieve → gate (refusal message) → generate → map chunks to `ChatSource`. Update `deps.py`.

### Task 6: End-to-end verification (golden questions)
- [ ] TestClient: paper-content Q, structured Q (ML in Karachi), time-scoped Q, unanswerable Q → must refuse. Restart backend, verify in UI via browser. Commit + push.
