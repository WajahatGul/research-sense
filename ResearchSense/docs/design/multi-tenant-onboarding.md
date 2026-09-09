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

**The Bahria workspace stays the public demo.** A visitor who has not signed up
browses it exactly as the site works today, so a prospective user can see a
fully populated portal (profiles, publications, analytics, the assistant) before
deciding to sign up. Nothing from that demo is copied into a new workspace: once
signed up, the user sees only their own institution's data, which starts empty
until they add it.

## 6. Filling the data

### 6a. Paste a CV
- The user pastes CV text (or uploads a CV PDF; we extract its text).
- A single extraction pass pulls out **as much as the CV contains**: name,
  current affiliation, department, designation, education, research areas, and
  the full publication list `(title, year, venue, DOI?)`.
- The result is shown in an **editable review form, not saved as final**. Every
  field and every publication row can be corrected, removed, or added by hand,
  and low-confidence values are flagged so the user knows what to check. Nothing
  is written to the workspace until the user accepts the form.
- This keeps the CV a fast starting point rather than a source of truth: the
  record stays accurate because the researcher, not the parser, has the last
  word.

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

## 10. Decisions (confirmed)

1. **Bahria is the public demo.** Anyone can browse the Bahria workspace without
   signing up, exactly as the site works today. It is the read-only showcase that
   demonstrates what a fully populated portal looks like.
2. **Any other institution must provide its own data.** Signing up creates a new,
   empty workspace for that institution. No Bahria records are ever visible
   inside it, and nothing is pre-filled from the demo.
3. **A workspace represents an institution**, with the person who signs up as its
   first researcher and owner. More researchers can be added to the same
   workspace later, so the model does not have to change to support a whole
   department or university.
4. **CV extraction is comprehensive but never final.** The system pulls out
   everything it can find (name, affiliation, department, education, research
   areas, and the full publication list) and presents all of it in an **editable
   review form**. The user can correct, delete, or add any field or publication,
   and nothing is saved until they accept it.
5. **Build the focused onboarding slice, not full multi-tenancy.** Refactoring
   every repository, the analytics, and the index for general multi-tenancy is a
   large change with no extra visible benefit. We implement only what the
   onboarding journey needs (Sections 5 and 6) and keep the rest as future work.
6. **Sign-up is by email and password.** A researcher from another institution is
   not in any directory we hold, so there is nothing to "claim" and no ORCID name
   to verify against. ORCID stays optional and is recorded on the profile if
   given. Bahria users keep the existing ORCID claim flow unchanged.
7. **Workspace data is written at run time and is not permanent on the free
   tier.** The Bahria corpus is committed to the repository, so it always
   survives; anything a new user creates is written to the running instance's
   disk, which the free hosting plan wipes on restart or redeploy. This is
   accepted for the demonstration (a workspace lasts for the session, which is
   all a live demo needs). Making it permanent later means either a paid
   persistent disk or moving the mutable records to a hosted database, and is
   recorded as future work rather than built now.
8. **The interface must read well with very little data.** A new workspace starts
   with a handful of papers, so empty and low-data states (charts, counts,
   directory, assistant) must look deliberate and explain what to add next,
   rather than appearing broken.

## 11. Scope for this stage

**In scope**
- Sign-up that creates an empty institution workspace, branded with its name.
- A first researcher profile for the person who signed up.
- Paste a CV, review and edit everything extracted, then accept it.
- Add a paper by DOI (reusing the existing verified-metadata pipeline).
- Profile, publications, derived research areas, analytics, and the assistant,
  all computed over that workspace only.

**Explicitly out of scope for now** (kept in the design as future work)
- Migrating the Bahria corpus into the workspace model; it stays as it is.
- Inviting colleagues, roles and permissions inside a workspace.
- Cross-workspace administration, billing, or a workspace directory.
- Permanent storage for user-created workspaces (see decision 7).
- PDF upload as a source of publication metadata; the DOI route and manual
  entry cover the demonstration.

---

With Sections 10 and 11 settled the design is complete and ready to implement.
The Bahria workspace is left exactly as it is and keeps serving as the public
demo, so the whole slice can be built and shipped without touching the live
portal.
