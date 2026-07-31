# ResearchSense — Quality Gauntlet (Design)

**Date:** 2026-07-31
**Status:** Approved (Approach A — gates-first with targeted tests)

## Goal

Surround all code changes (human or agent) with enforced constraints, per the
"extreme constraints" methodology: unit tests, Gherkin BDD acceptance tests,
lint/type quality gates, a coverage floor, one gauntlet runner, and CI
enforcement. Constraints exist and fail loudly from day one; strictness
ratchets upward over time.

**Explicitly out of scope:** mutation testing (poor Windows tooling, hours per
run — revisit if the project moves to Linux CI-only enforcement), E2E browser
tests, load tests.

## Decisions made with the user

- **Scope:** pragmatic gauntlet — unit + BDD + ruff + coverage floor +
  frontend vitest/eslint/tsc. No mutation testing.
- **Enforcement:** local single-command runner AND GitHub Actions on push/PR.
- **Sequencing:** own plan, executed after the supervisor-feedback plan's
  Task 17 + final review close out.

Decisions made by the implementer-side design (not user-visible choices):
- BDD via **pytest-bdd** with real `.feature` files (rides existing pytest).
- Coverage floor = **measured at setup, rounded down to the nearest whole
  percent**, hardcoded into config; the ratchet rule (floor only moves up)
  lives in docs/QA.md.

## Components

### 1. Backend gates (`ResearchSense/backend/`)

- **ruff** — lint + `ruff format --check`; config in a new `pyproject.toml`
  (line length 88, target py313, rule set: `E,F,W,I,UP,B,SIM`; per-file
  ignores where the existing code legitimately deviates rather than mass
  refactoring). `app/`, `scripts/`, `tests/` must pass.
- **pytest + pytest-cov** — coverage over `app/` and `scripts/`,
  `--cov-fail-under=<floor>`. Slow/network paths (`scrape_bahria` main,
  network fetchers) excluded via `# pragma: no cover` on the thin network
  wrappers only — pure logic is never exempted.
- **BDD acceptance tests** — `tests/features/*.feature` (Gherkin) +
  `tests/steps/` step definitions (pytest-bdd), running against FastAPI
  TestClient with tmp-path SQLite and monkeypatched staging/embedding (the
  suite's existing pattern). Six scenarios:
  1. Faculty submits a paper → it is pending, not publicly visible.
  2. Admin approves → paper visible in publications + counted on profile.
  3. Admin rejects with a note → paper stays hidden; faculty sees the note.
  4. Collaborator suggestions require a real signal and honor `sort=`.
  5. Publications filter by year range + department + paper type.
  6. Researcher names contain no honorific prefixes.

### 2. Frontend gates (`ResearchSense/frontend/`)

- **vitest + @testing-library/react + jsdom** — component tests for:
  Collaboration page states (loader / stale-placeholder-scoping / empty),
  AdminPanel pending queue (render rows, approve/reject calls, note input),
  chart components' empty-state rendering.
- **eslint** — flat config, `typescript-eslint` recommended set, react-hooks
  plugin; `npm run lint`.
- **tsc** — existing `tsc -b` stays the type gate (part of `npm run build`).

### 3. Gauntlet runner

`ResearchSense/backend/scripts/gauntlet.py` (`python -m scripts.gauntlet`):
runs, in order — backend ruff → backend pytest with coverage floor →
frontend eslint → frontend vitest → frontend build (tsc + vite). Prints a
gate-by-gate pass/fail table, exits non-zero on first failure. Flags:
`--backend-only` / `--frontend-only` for focused runs.

### 4. CI

`.github/workflows/gauntlet.yml` — two parallel jobs (backend: Python 3.13;
frontend: Node 20) on push + pull_request, with pip/npm caching. Jobs run
the same commands as the local runner (no CI-only logic). A failing gate
fails the workflow.

### 5. QA procedure

`docs/QA.md` — the gauntlet contract: what runs locally and in CI, what
blocks a merge, the coverage-ratchet rule, how to add a BDD scenario, and
the rule that no gate may be weakened (floor lowered, rule disabled) without
an explicit note in the commit message explaining why.

## Error handling / edge cases

- The runner must work on Windows (Git Bash and PowerShell) and Linux (CI):
  use `sys.executable`/`npm.cmd`-aware subprocess calls, never shell=True
  string commands with POSIX-isms.
- vitest introduction must not break `npm run build` or the Vercel/HF
  deploys: test files live in `src/**/*.test.tsx`, excluded from `tsc -b`
  build via tsconfig `exclude` if needed.
- pytest-bdd scenarios reuse existing fixtures; no live data files or
  network in any gate.
- Coverage floor is measured with the full suite green; if measurement and
  gate disagree later, the gate (config value) is the authority.

## Testing the gauntlet itself

- Runner: a unit test asserting gate ordering and non-zero exit on a
  simulated failing gate (subprocess calls monkeypatched).
- CI: verified by pushing the branch and observing a green workflow run
  (documented as a manual verification step; if no GitHub remote is
  configured, the workflow file ships and the step is recorded as pending).
