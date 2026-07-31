# ResearchSense — Supervisor Feedback Upgrade (Design)

**Date:** 2026-07-31
**Status:** Approved (Approach A — data-first, phased)

## Goal

Address all seven supervisor SRS points plus two additional requirements
(fluid adaptive UI; expansion beyond computing departments), delivered in
phases so the expensive data pipeline runs once and every downstream feature
reads precomputed data.

| # | Requirement | Design section |
|---|-------------|----------------|
| 1 | Collaborator sorting | §4 |
| 2 | Research area accuracy | §2 |
| 3 | Names without honorifics | §1 |
| 4 | Accurate collaborator suggestions | §4 |
| 5 | Visualization improvements | §6 |
| 6 | International collaboration | §3 |
| 7 | Admin approval workflow for papers | §5 |
| + | Fluid/adaptive UI (clamp) | §7 |
| + | All departments, all campuses | §1 |

## Decisions made with the user

- **Department scope:** all departments across all four campuses, but a
  *sample of ~12 faculty per (campus, department)* for now, behind a single
  config constant so a later upgrade to full faculty is a one-line change.
- **Approval scope:** only faculty-portal submissions require admin approval.
  Scraped/OpenAlex publications stay auto-published. Existing submissions are
  grandfathered as approved.
- **Collaborator sorting:** improved relevance default **plus** a visible
  sort dropdown (relevance · shared areas · co-authored papers · name A–Z ·
  campus).
- **Research areas:** hybrid — derived from OpenAlex topics of the person's
  actual publications, falling back to cleaned directory expertise when they
  have no indexed papers.

## Phasing (Approach A)

1. **Phase 1 — pipeline:** scraper + seed + fetch changes (§1–§3), then run
   scrape → seed → fetch → download → index once in the background.
2. **Phase 2 — backend:** suggestions + sorting API, approval workflow,
   new analytics endpoints (§4–§6 backend halves).
3. **Phase 3 — frontend:** sort UI, admin queue, visualization upgrades,
   fluid UI (§4–§7 frontend halves).

Rationale: research-area accuracy, suggestion quality, international flags,
and the new charts all consume the same new pipeline fields; running the
pipeline once avoids hours of repeated background work.

---

## §1 Data expansion + name formatting (SRS 3, dept expansion)

**Scraper** (`backend/scripts/scrape_bahria.py`):
- Remove the computing-only regex filter; keep every department across the
  four teaching campuses. Normalize department display names (title case,
  dedupe obvious variants).

**Seed build** (`backend/scripts/build_seed.py`):
- `FACULTY_PER_DEPT = 12` — sample cap per (campus, department). Selection
  prefers faculty with listed research areas, then senior designations
  (Professor > Associate > Assistant > Lecturer), because they are the most
  likely to have findable publications. Setting the constant to `None` later
  means "everyone".
- `normalize_name(raw) -> str`: strips leading honorifics — Dr, Prof,
  Professor, Engr, Mr, Ms, Mrs, and stacked combinations ("Prof Dr") — with
  or without trailing dots. Applied once at seed-build time; 125 of the
  current 225 scraped names carry titles. Downstream code and UI never
  strip titles themselves. Unit-tested.

**Non-goals:** no new scraping sources; the university directory remains the
single faculty roster source.

## §2 Research areas — hybrid derivation (SRS 2)

**Fetch** (`backend/scripts/fetch_publications.py`):
- Already pulls OpenAlex works per researcher. Additionally capture each
  work's `topics` (OpenAlex topic display names) into the publication
  record.

**Derivation** (in the seed/fetch pipeline, stored in `researchers.json` and
`topics.json`):
- A researcher's areas = top-N (N=5) OpenAlex topic names across their
  publications, ranked by frequency then recency.
- Fallback for researchers with no indexed publications: directory
  expertise cleaned through a normalization map — split compound strings on
  `,;/&`, trim, canonicalize common variants ("ML" → "Machine Learning",
  "AI" → "Artificial Intelligence", case-folding dupes).
- `topics.json` is rebuilt from the union of derived areas; topic pages and
  filters use the normalized names.

## §3 International collaboration (SRS 6)

- During the OpenAlex fetch, read each work's `authorships[].institutions`
  (name + `country_code`).
- Per publication store: `coauthor_institutions: [{name, country}]` and
  `international: bool` (true when any institution's country ≠ PK).
- Per researcher (derived at pipeline time): list of distinct international
  partner institutions with countries.
- Surfaced in: researcher profile (partner-institution list), collaboration
  page (international badge on collaborators), analytics (international vs
  domestic split, §6).
- Publications with no institution metadata count as domestic (no false
  international claims).

## §4 Collaborator suggestions — accuracy + sorting (SRS 1, 4)

**Accuracy** (`app/repositories/mock/researchers.py`,
`_collaborators_for`):
- A suggestion requires a real signal: ≥1 co-authored paper OR ≥1 shared
  *normalized* research area. The weak Jaccard-only tail is dropped; the
  list is no longer padded toward 15.
- Same-name/false-positive guard from the fetch stage remains.
- Each suggestion keeps its explanation payload (shared area names,
  co-authored count) so the UI can justify every match.

**Sorting:**
- Default relevance score: co-authored papers weighted heaviest, then
  shared-area count, then area-specificity (rarer shared areas score
  higher than ubiquitous ones).
- API: `GET .../collaborators?sort=relevance|shared_areas|coauthored|name|campus`
  (default `relevance`). Sorting happens server-side on precomputed fields.
- Frontend: visible sort dropdown on the collaboration page; existing
  campus/area filters remain.

## §5 Admin approval workflow (SRS 7)

**Data** (SQLite):
- Submission records gain `status: pending | approved | rejected`,
  `submitted_at`, `reviewed_at`, and an optional reviewer note.
- Migration: all existing submissions become `approved`.

**Submission flow** (`app/services/submission_service.py`):
- On submit: store the record as `pending`. Chunking + embedding run
  immediately in a background task into **staged** chunks (stored alongside
  but excluded from the live index). The paper does *not* appear in
  `publications.json`, profiles, search, or the chatbot.
- On **approve**: publish the record into `publications.json` (and the
  durable submissions store) and merge its staged chunks into the live RAG
  index — go-live is immediate because the expensive work already happened.
- On **reject**: record kept with status + note for the faculty member;
  staged chunks discarded.

**API** (`app/routers/admin.py`): pending-queue list, approve, reject —
admin-authenticated like the existing admin endpoints.

**Frontend:**
- Admin portal: "Pending papers" queue showing title, submitter, venue,
  DOI/metadata, with approve/reject actions.
- Faculty portal: each submission shows its status (pending / published /
  rejected with note).

## §6 Visualization improvements (SRS 5)

- **New dimension — department:** analytics gain department as a grouping
  (publications by department, top departments), since the corpus is no
  longer CS-only.
- **New chart — international vs domestic collaboration** (from §3 flags).
- **Collaboration network cleanup:** node cap with "top collaborations"
  selection, edge width by co-authorship count, hover labels, colors stable
  per entity (extend the existing campus palette approach to departments).
- **Readability pass on existing charts:** axis/legend clarity, empty-state
  handling, consistent tooltip formatting.
- Implementation follows the dataviz design-system skill (form, palette
  validation, light/dark).

## §7 Fluid adaptive UI (clamp)

- Global CSS custom properties in the shared styles layer:
  - Type scale: `--fs-0`…`--fs-6` as `clamp(min, base + vw-term, max)`.
  - Space scale: `--sp-1`…`--sp-8`, same technique.
- Module CSS files replace fixed px font sizes and key paddings/margins
  with the scale variables; container widths become fluid
  (`min(100% - 2*var(--sp-4), 72rem)` pattern).
- Grid audit for narrow screens (researcher cards, analytics grid, admin
  tables → horizontal scroll containers where needed).
- No framework or build-tool change.

## §8 Background pipeline run + performance discipline

- After Phase 1 lands: run `scrape_bahria → build_seed →
  fetch_publications → download_papers → build_index` as a background task
  on the dev machine while Phases 2–3 proceed. The weekly refresh job and
  the admin "Refresh data now" path are updated to carry the new fields.
- **Performance principles applied:**
  - Targets first: list endpoints p95 < 300 ms locally; chatbot behavior
    unchanged.
  - Everything derivable is computed at pipeline time (areas, international
    flags, suggestion inputs) — request handlers only read and sort.
  - Measure before/after any optimization; no speculative micro-tuning.
  - Respect repo conventions: routers thin, repositories own data access,
    files ≤ ~350 lines.

## §9 Testing

The backend currently has no test suite; this work introduces one
(`backend/tests/`, pytest) covering the new pure logic:
- `normalize_name` — titles, stacked titles, dot variants, names that
  legitimately start with title-like substrings.
- Per-department sampling — cap respected, preference ordering, `None` =
  everyone.
- Area derivation — publication-topic ranking, fallback path, variant
  canonicalization.
- International flag — non-PK institution detection, missing-metadata
  default to domestic.
- Suggestion ranking + signal threshold — ordering under each `sort` value,
  weak matches excluded.
- Approval state machine — pending → approved publishes + merges chunks;
  pending → rejected discards staged chunks; grandfathering migration.

Frontend behavior is verified manually (sort dropdown, admin queue, fluid
layout at narrow/wide widths) — consistent with the project's existing
practice of not having a frontend test suite.

## Error handling notes

- Scraper: departments/rows that fail detail-page fetch keep directory data
  (existing behavior), never abort the run.
- OpenAlex fetch: missing topics/institutions degrade gracefully (fallback
  expertise; domestic default).
- Approval endpoints are idempotent: approving an already-approved paper is
  a no-op, not an error.
- Staged chunks for rejected papers are deleted on rejection and swept on
  index rebuild (no orphan growth).
