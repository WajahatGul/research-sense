# Design: Self-service onboarding and multi-tenant workspaces

Status: **proposal for review** (no code yet)
Author: prepared for WajahatGul / Ammar
Date: 2 August 2026

## 1. Goal

Let a researcher from **any** university sign up, get their **own** space, and
build their profile and analytics from **their own data** — not Bahria's. They
should be able to:

- create their own researcher profile (name, institution, department, campus);
- **paste a CV** and have the system fill in their profile and publication list;
- **add papers** (by DOI or by uploading a PDF) that become their publications;
- see analytics and ask the assistant, all computed over **their** data only.

A new user must never see Bahria's records, and Bahria's live portal must keep
working exactly as it does today.

## 2. Where we are now (single-tenant)

Today the product holds **one** dataset:

- Research corpus in JSON files: `researchers.json`, `publications.json`,
  `projects.json`, `topics.json` (Bahria's 358 researchers).
- Mutable data in SQLite (`researchsense.db`): `accounts`, `uploads`,
  `submissions`.
- One RAG index: `rag_chunks.json` + `rag_index.npz`.
- Repositories read the JSON; services hold logic; routers expose the API.
- A user "claims" an **existing** Bahria profile with ORCID — there is no way to
  create a brand-new profile for someone not already in the data.

So there is no notion of a separate space per user, and no self-service profile
creation. Both are needed.

## 3. Core idea: the Workspace

Introduce a **Workspace** (a tenant). A workspace owns its own researchers,
publications, projects, topics, and its own search index. Everything a user
sees is scoped to their workspace.

- **Bahria University** becomes the first workspace, pointing at the data that
  exists today — so nothing about the current site changes.
- A new signup creates a **new, empty workspace** whose institution name is set
  from what the user types, and a researcher profile for that user inside it.

Two isolation strategies were considered:

| Approach | Isolation | Effort | Notes |
|---|---|---|---|
| A directory per workspace (`data/workspaces/<id>/…json`, `…/index`) | Strong (files never mix) | Lower | No record-schema change; the loader just picks the workspace folder. **Recommended.** |
| A `workspace_id` column on every record + shared files | Weaker (filter everywhere) | Higher | Easy to leak data if a query forgets the filter. |

**Recommendation: a folder per workspace.** The existing Bahria files move under
`data/workspaces/bahria/` (or a symlink/default keeps them in place), and each
new workspace gets its own folder created at signup.

## 4. Data model changes

Add to SQLite:

- `workspaces(workspace_id, name, institution_name, campus_label, owner_account_id, created_at)`
- `accounts` gains `workspace_id` (which space the account belongs to).
- `submissions`, `uploads` gain `workspace_id`.

Per-workspace on disk (created at signup):

```
data/workspaces/<id>/
  researchers.json      publications.json     projects.json
  topics.json           rag_chunks.json       rag_index.npz
  papers/…              staged/…
```

The retriever, analytics, and repositories take a `workspace_id` (resolved from
the signed-in user, or the default Bahria workspace for anonymous/public views).

## 5. Onboarding flow (new user)

1. **Sign up** on a new "Create your workspace" form: email, password,
   institution name, your name, department, campus (optional), ORCID (optional).
2. The system creates: a workspace (branded with their institution name), an
   account, and a first researcher profile (the user) inside it.
3. They land on their **empty** portal, branded for their institution, with a
   "Build your profile" panel.

Existing Bahria users are unaffected: they still "claim" a Bahria profile.

## 6. Filling the data

### 6a. Paste a CV
- The user pastes CV text (or uploads a CV PDF; we extract its text).
- A single LLM call (Groq, which we already use) extracts structured fields:
  name, current affiliation, department, education, research areas, and a list
  of publications `(title, year, venue, DOI?)`.
- The result **pre-fills** the profile and proposes publication rows for the
  user to confirm — never auto-committed blindly, to keep the record honest.

### 6b. Add papers
- **By DOI:** reuse the existing DOI pipeline (Crossref/DataCite/OpenAlex) to
  fetch verified metadata.
- **By PDF upload:** extract text; take title/authors from the PDF metadata when
  present, else one LLM pass over the first page; the user confirms.
- Confirmed papers are written to the workspace's `publications.json`, topics
  are derived, and the chunks are embedded into the workspace index.

### 6c. Derived research areas & analytics
- Research areas are computed from the user's own papers (same logic as today).
- Analytics (per year, by topic, venues, international split) are recomputed over
  the workspace's own publications.

## 7. Per-workspace assistant

- The retriever loads `data/workspaces/<id>/rag_index.npz`.
- All chat fast paths and RAG answer from the workspace's own researchers and
  publications; the assistant identifies itself with the workspace's institution
  name.
- A brand-new workspace with a few papers has a tiny index that builds in
  seconds — no heavy rebuild, friendly to the free tier.

## 8. Migration plan (keep Bahria live at every step)

1. **Introduce the Workspace layer, default everything to "bahria".** Move the
   current files under a `bahria` workspace; the loader/retriever default to it.
   No user-visible change. Ship + verify Bahria works unchanged.
2. **Scope the data/analytics/index layer by workspace id** (public views use
   the Bahria workspace).
3. **Add the signup + create-workspace flow** and workspace context in the UI.
4. **Add ingestion**: DOI, PDF upload, and CV paste writing into the user's
   workspace, with confirm-before-commit.
5. **Per-workspace analytics + chatbot index.**

Each step is its own branch and PR into `main`, tested locally first.

## 9. Risks and open questions

- **Free-tier resources:** many workspaces each with an index means more disk and
  memory; per-workspace indexes are small, but we should cap workspace size for
  the demo.
- **CV extraction accuracy:** LLM extraction can miss or mis-read entries; the
  confirm step is essential, and we should show the user exactly what was found.
- **PDF metadata quality:** many PDFs lack clean metadata; the LLM fallback and a
  manual-entry option cover this.
- **Data honesty:** the "coverage is limited" and "sample" notices must carry
  over so a new workspace never over-claims.
- **Scope for the FYP:** full multi-tenancy is several iterations. A good first
  milestone is Sections 5 + 6 (self-service profile + CV/paper ingestion) inside
  a single new workspace, which is fully demoable.

**Open questions for you:**
1. Is a workspace **one researcher's space**, or a whole **institution** (many
   researchers, admin-managed)? The design supports both; the MVP assumes the
   former.
2. Should anonymous visitors still see the Bahria portal by default, with signup
   creating a private workspace? (Assumed yes.)
3. How much CV auto-fill do you want to trust vs. always confirm? (Assumed:
   always confirm.)

---

Nothing here is built yet. Once you're happy with the approach (and answer the
open questions), the recommended first slice to implement is **Sections 5 and 6
in one new workspace** — self-service profile + CV/paper ingestion — which is a
concrete, demoable step toward the full product.
