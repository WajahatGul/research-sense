# Single-image deploy for a Hugging Face Docker Space (free, no card).
# Stage 1 builds the React frontend; stage 2 runs FastAPI and serves that
# build, so one container serves the whole app on one URL (no CORS, no proxy).

# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY ResearchSense/frontend/package.json ResearchSense/frontend/package-lock.json ./
RUN npm ci
COPY ResearchSense/frontend/ ./
RUN npm run build

# --- Stage 2: Python backend + the built frontend ---
FROM python:3.13-slim AS app
WORKDIR /app

COPY ResearchSense/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ResearchSense/backend/ ./
COPY --from=frontend /fe/dist ./frontend_dist

# Serve the built frontend from FastAPI (see app.core.app._mount_frontend).
ENV FRONTEND_DIST=/app/frontend_dist
# Writable caches (HF Spaces run as a non-root user with $HOME=/app).
ENV HF_HOME=/app/.cache
ENV FASTEMBED_CACHE=/app/.fastembed_cache

# Bake the embedding model into the image so the first chat has no cold
# download (the retriever caches to /app/.fastembed_cache).
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/app/.fastembed_cache')"

# Make the app dir writable (SQLite, uploads, index writes) for HF's user.
RUN chmod -R 777 /app

# Hugging Face Spaces route to port 7860.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
