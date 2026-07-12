---
title: ResearchSense
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# ResearchSense

A research information system for Bahria University — researcher profiles,
publications, research areas, funded projects, a collaboration finder, an
analytics dashboard, a faculty portal, and a grounded AI research assistant.

The full app (React frontend + FastAPI backend + agentic RAG chatbot) runs as
one container; this repo is deployable free on a Hugging Face Docker Space.
See [ResearchSense/DEPLOY.md](ResearchSense/DEPLOY.md) for deployment, and
[ResearchSense/README.md](ResearchSense/README.md) for architecture and the
local-development setup.

The metadata block at the top of this file configures the Hugging Face Space
(Docker SDK, port 7860); it is harmless elsewhere.
