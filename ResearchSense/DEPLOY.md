# Deploying ResearchSense (free tier)

Frontend on **Vercel**, backend on **Render**, chatbot on **Groq** (all free).
The React app calls same-origin `/api/*`, which Vercel proxies to Render — so
there is no CORS to configure and every request (including auth uploads) works.

```
Browser ──/api──► Vercel (static site + proxy) ──► Render (FastAPI) ──► Groq
```

## What works vs. what resets on the free tier

- **Works fully:** the whole read-only site (researchers, publications,
  analytics, collaboration finder) and the chatbot — the RAG index ships in
  the repo, so no data pipeline runs on deploy.
- **Resets on redeploy / idle spin-down:** claimed accounts, uploaded papers,
  DOI submissions, and library additions (Render's free disk is ephemeral).
  Fine for a demo; for permanence use a Render **paid disk** or a hosted
  Postgres.

---

## Step 1 — Rotate the Groq keys (do this first)

The keys currently in `backend/.env` have been shared during development.
Generate fresh ones at <https://console.groq.com/keys>. Never commit `.env`
(it is gitignored). You will paste the new keys into Render, not the repo.

## Step 2 — Deploy the backend to Render

1. Push this repo to GitHub (see Step 4 if you have not yet).
2. <https://render.com> → **New +** → **Blueprint** → connect the repo.
   Render reads `render.yaml` at the repo root and configures the service.
3. When prompted, set the secret env vars:
   - `GROQ_API_KEY` (and optionally `GROQ_API_KEY_2..4`) — your new keys
   - `ADMIN_USERNAME` (e.g. `admin`), `ADMIN_PASSWORD` (a real password)
4. Deploy. First build takes a few minutes. When live you get a URL like
   `https://researchsense-api.onrender.com`.
5. Verify: open `https://<your-render-url>/api/health` → `{"status":"ok"}`.

> Cold start: the free service sleeps after ~15 min idle; the next request
> takes ~50 s to wake, and the first chat also downloads the embedding model.
> Open the site once before a demo to warm it.

## Step 3 — Deploy the frontend to Vercel

1. Edit `ResearchSense/frontend/vercel.json` and replace
   `https://researchsense-api.onrender.com` with **your** Render URL (both are
   the same host). Commit and push.
2. <https://vercel.com> → **Add New** → **Project** → import the repo.
3. Set **Root Directory** to `ResearchSense/frontend`. Vercel auto-detects
   Vite (build `npm run build`, output `dist`). No env vars needed.
4. Deploy. You get a URL like `https://research-sense.vercel.app` — that is
   the live app.

## Step 4 — Push the repo (if not already on GitHub)

```bash
# from the repo root
git push origin feature/agentic-rag-pipeline
# or merge to main first, then: git push origin main
```

Render and Vercel redeploy automatically on every push to the connected branch.

---

## Notes

- **Memory:** Render free is 512 MB. The embedding model + index fit, but if
  the service OOMs on the first chat, upgrade to the next Render tier.
- **CORS:** not needed because of the Vercel proxy. `RS_CORS_ORIGINS` stays
  permissive as a safety net only.
- **Developer bypass:** leave `DEV_ORCID` unset in production so profile
  claims require a real ORCID identity check.
