# ResearchSense Grounded RAG Chatbot — Design

**Date:** 2026-07-10
**Status:** Approved
**Scope:** Replace the keyword chat shell with a retrieval-augmented chatbot that
answers only from ResearchSense data and real faculty papers, refusing anything
it cannot ground. Zero running cost. MVP paper corpus: 10–20 open-access papers
by Dr. Arif ur Rahman; scale to all faculty later.

## 1. Non-negotiables and how they are enforced

Hallucination is prevented by the pipeline, not by trusting the model:

1. **Retrieval gate.** The question is embedded and matched against the index.
   Best score below threshold → fixed refusal answer; the LLM is never called.
2. **Context-only prompting.** Groq (Llama 3.3 70B, temperature 0) receives only
   retrieved chunks and must answer solely from them; if the context does not
   contain the answer it must output the refusal token `NO_ANSWER`.
3. **Refusal token check.** `NO_ANSWER` → honest "not in my data" message.
4. **Sources from retrieval, not the model.** UI source chips are the actual
   retrieved records.
5. **Extractive fallback.** Missing key / Groq error / rate limit → grounded
   extractive answer assembled directly from retrieved chunks. Never breaks,
   never costs money.

## 2. Corpus

- **Structured facts:** all researcher profiles (expertise, education, campus,
  email), real publications (title/venue/year/citations/co-authors), projects,
  topics.
- **Full paper text (MVP):** `backend/papers/` holds 10–20 real open-access
  PDFs by Dr. Arif ur Rahman, discovered and downloaded via OpenAlex
  (`best_oa_location.pdf_url`). Text extracted with pypdf, chunked ~800 chars
  with overlap, tagged with paper title + DOI.

## 3. Zero-cost stack

- **Embeddings:** fastembed running all-MiniLM-L6-v2 locally (ONNX, CPU, free).
- **Vector store:** numpy arrays in `app/data/rag_index.npz` +
  `rag_chunks.json`. ~1.5k chunks → in-memory cosine similarity is instant.
- **LLM:** Groq free tier via plain HTTPS (no SDK). `GROQ_API_KEY` in
  `backend/.env` (git-ignored), loaded with python-dotenv.

## 4. Architecture

```
scripts/download_papers.py → papers/*.pdf + papers/manifest.json   (one-time)
scripts/build_index.py     → app/data/rag_chunks.json + rag_index.npz

app/services/rag/retriever.py  query embedding → top-k + scores → gate
app/services/rag/generator.py  Groq call (strict prompt) | extractive fallback
app/services/chat_service.py   retrieve → gate → generate → cite
```

`ChatResponse` contract unchanged; frontend chat UI needs no changes. Chunk
metadata carries `{kind, ref_id, label}` mapping directly to `ChatSource`
(kinds: researcher, publication, paper, project, topic).

## 5. Testing (golden questions, end-to-end)

1. Answerable from a downloaded paper (content question) → grounded answer + paper source.
2. Structured: "who works on machine learning in Karachi?" → correct names.
3. Time-scoped: "what did <faculty> publish in 2022?" → correct list.
4. Unanswerable: "what is Dr. Arif ur Rahman's salary?" → refusal, no invention.

## 6. Out of scope (later phases)

Papers for all faculty (same pipeline, larger corpus), conversation memory,
answer streaming, reranker models.
