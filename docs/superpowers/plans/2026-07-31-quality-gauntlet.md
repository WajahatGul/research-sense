# Quality Gauntlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforced quality gates around all ResearchSense code — ruff lint, pytest coverage floor, Gherkin BDD acceptance tests, frontend vitest/eslint, a single gauntlet runner, and GitHub Actions CI — per the approved spec at `docs/superpowers/specs/2026-07-31-quality-gauntlet-design.md`.

**Architecture:** Gates-first: every gate stands up now and fails loudly; new tests target only the highest-risk behavior (six BDD user flows, four frontend components). The coverage floor is measured, hardcoded, and only ever ratchets up. Local runner and CI execute identical commands.

**Tech Stack:** ruff, pytest-cov, pytest-bdd (backend, Python 3.13); vitest + @testing-library/react + jsdom, eslint 9 flat config + typescript-eslint (frontend, Node); GitHub Actions.

## Global Constraints

- Backend commands run from `ResearchSense/backend/` with `.venv/Scripts/python` (Windows Git Bash); frontend from `ResearchSense/frontend/`.
- No gate may depend on the network or on live data files (`app/data/*.json` may be regenerated at any time — tests use tmp_path/inline fixtures only, matching the existing suite).
- Coverage enforcement lives in the gauntlet/CI commands, NOT in pytest addopts (single-test dev runs stay fast). The floor value appears in exactly one place: `pyproject.toml` `[tool.gauntlet]`-style comment + the runner reads it from `pyproject.toml` — see Task 5.
- The runner must work on Windows and Linux: `sys.executable` for Python, `npm.cmd` fallback on Windows, no `shell=True` POSIX-isms.
- vitest/test files must not enter the production build: they live in `src/**/*.test.tsx` and `src/test/`, excluded in `tsconfig.json`.
- Files ≤ ~350 lines; existing repo conventions (thin routers, repository data access) are unchanged by lint fixes — `ruff --fix` may not alter behavior; anything non-auto-fixable gets a scoped per-file-ignore rather than a risky hand refactor.
- All existing tests (81+ at time of writing) stay green after every task.
- Do not stage/commit `app/data/*.json`, `*.npz`, or `papers/` artifacts in any task.

---

### Task 1: Backend lint gate (ruff)

**Files:**
- Create: `ResearchSense/backend/pyproject.toml`
- Modify: `ResearchSense/backend/requirements-dev.txt`
- Modify: whatever `ruff check --fix` + `ruff format` safely auto-fix under `app/`, `scripts/`, `tests/`

**Interfaces:**
- Produces: `ruff check app scripts tests` and `ruff format --check app scripts tests` both exit 0 from `ResearchSense/backend/` — Tasks 5 and 6 run these exact commands.

- [ ] **Step 1: Add ruff to dev requirements and install**

Append to `requirements-dev.txt`:
```
ruff>=0.6
pytest-cov>=5
pytest-bdd>=7
```
Run: `cd ResearchSense/backend && .venv/Scripts/python -m pip install -r requirements-dev.txt`

- [ ] **Step 2: Create pyproject.toml with the ruff config**

```toml
[tool.ruff]
line-length = 88
target-version = "py313"
extend-exclude = [".venv", "papers"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
# The app predates the linter; ignores below keep the gate honest without
# rewriting working code. Remove entries as files get cleaned up.
ignore = ["B008"]  # FastAPI Depends() in defaults is idiomatic

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["SIM117"]

[tool.coverage.run]
source = ["app", "scripts"]
omit = ["app/data/*", "scripts/scrape_bahria.py"]

# Gauntlet coverage floor — the runner and CI read this value; it may only
# ever increase. See docs/QA.md.
[tool.gauntlet]
coverage_floor = 0  # placeholder; Task 2 measures and sets the real floor
```

- [ ] **Step 3: Auto-fix and survey the remaining violations**

Run: `.venv/Scripts/python -m ruff check app scripts tests --fix` then `.venv/Scripts/python -m ruff format app scripts tests` then `.venv/Scripts/python -m ruff check app scripts tests --statistics`.
For each remaining rule family, decide: trivially safe manual fix (unused import, f-string) → fix it; behavior-adjacent (B, SIM logic rewrites) → add a `per-file-ignores` entry instead. The gate must end at zero findings without any behavior change.

- [ ] **Step 4: Prove no behavior change**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: all tests pass (same count as before this task).
Run: `.venv/Scripts/python -m ruff check app scripts tests && .venv/Scripts/python -m ruff format --check app scripts tests && echo GATE-CLEAN`
Expected: `GATE-CLEAN`.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/pyproject.toml ResearchSense/backend/requirements-dev.txt ResearchSense/backend/app ResearchSense/backend/scripts ResearchSense/backend/tests
git commit -m "chore: ruff lint gate (auto-fixes + scoped ignores), zero findings"
```
(Verify with `git status` that no `app/data/` files were swept in; unstage them if so.)

---

### Task 2: Coverage gate with measured floor

**Files:**
- Modify: `ResearchSense/backend/pyproject.toml` (set the real `coverage_floor`)

**Interfaces:**
- Produces: `pyproject.toml` `[tool.gauntlet] coverage_floor = <N>` where `<N>` is the measured whole percent, and the command `python -m pytest tests/ --cov=app --cov=scripts --cov-fail-under=<N> -q` exits 0. Tasks 5 and 6 build this command by reading the value.

- [ ] **Step 1: Measure current coverage**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ --cov=app --cov=scripts -q`
Note the TOTAL percent from the report (call it P).

- [ ] **Step 2: Set the floor**

Edit `pyproject.toml`: `coverage_floor = <floor(P)>` (round DOWN to a whole percent — the suite must pass its own gate on day one).

- [ ] **Step 3: Verify the gate passes and would fail if raised**

Run: `.venv/Scripts/python -m pytest tests/ --cov=app --cov=scripts --cov-fail-under=<floor> -q` → exit 0.
Run: `.venv/Scripts/python -m pytest tests/ --cov=app --cov=scripts --cov-fail-under=99 -q; echo "exit=$?"` → non-zero exit (proves enforcement works).

- [ ] **Step 4: Commit**

```bash
git add ResearchSense/backend/pyproject.toml
git commit -m "chore: coverage gate with measured floor"
```

---

### Task 3: BDD acceptance tests (pytest-bdd)

**Files:**
- Create: `ResearchSense/backend/tests/features/approval.feature`
- Create: `ResearchSense/backend/tests/features/discovery.feature`
- Create: `ResearchSense/backend/tests/steps/__init__.py` (empty)
- Create: `ResearchSense/backend/tests/steps/test_approval_steps.py`
- Create: `ResearchSense/backend/tests/steps/test_discovery_steps.py`

**Interfaces:**
- Consumes: existing fixture patterns from `tests/test_admin_approval.py` (tmp-path DB via `monkeypatch.setattr(accounts_mod, "DB_PATH", ...)`, `AccountStore._instance = None`, `app.dependency_overrides[security.current_admin]`), `tests/test_collaborators.py` (FakeRepo), and monkeypatched `staging`/`publish_record` — read those files first and reuse their idioms.
- Produces: `pytest tests/steps -q` green; scenarios discoverable by plain `pytest tests/`.

- [ ] **Step 1: Write the feature files**

`tests/features/approval.feature`:
```gherkin
Feature: Admin approval workflow for faculty papers
  Faculty submissions stay hidden until an admin approves them.

  Scenario: Submitted paper is pending and not published
    Given a faculty submission titled "Fog Computing Survey"
    Then the submission status is "pending"
    And the pending queue lists "Fog Computing Survey"
    And nothing has been published

  Scenario: Approval publishes the paper and merges its staged chunks
    Given a faculty submission titled "Fog Computing Survey"
    When an admin approves the submission
    Then the submission status is "approved"
    And the record was published
    And the staged chunks were merged

  Scenario: Rejection hides the paper and records the note
    Given a faculty submission titled "Fog Computing Survey"
    When an admin rejects the submission with note "duplicate of DOI 10.1/x"
    Then the submission status is "rejected"
    And the staged chunks were discarded
    And the faculty member can read the note "duplicate of DOI 10.1/x"
```

`tests/features/discovery.feature`:
```gherkin
Feature: Research discovery quality
  Suggestions, filters, and naming meet the supervisor's requirements.

  Scenario: Collaborator suggestions require a real signal and honor sorting
    Given a roster where only some researchers share areas or papers
    Then no suggestion lacks both a shared area and a co-authored paper
    And sorting by "name" returns suggestions in alphabetical order
    And the default order puts a past co-author first

  Scenario: Publications filter by period, department, and type
    Given publications from several departments, years, and types
    Then filtering years 2019-2020 for "Psychology" conference papers matches only such records

  Scenario: Researcher names carry no honorifics
    Given the seed name normalizer
    Then "Dr.Sana Aroos Khattak" is stored as "Sana Aroos Khattak"
    And "Prof Dr Saad Alvi" is stored as "Saad Alvi"
```

- [ ] **Step 2: Run to verify scenarios fail (no step definitions yet)**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/steps -q`
Expected: errors/failures — step definitions missing (or no tests collected; then proceed, the binding test files come next).

- [ ] **Step 3: Write the step definitions**

`tests/steps/test_approval_steps.py`:
```python
import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import app.repositories.accounts as accounts_mod
from app.repositories.accounts import AccountStore

scenarios("../features/approval.feature")


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "bdd.db")
    AccountStore._instance = None
    import app.routers.admin as admin_mod

    state = {"published": [], "merged": [], "discarded": []}
    monkeypatch.setattr(
        admin_mod.submission_service, "publish_record",
        lambda rec: state["published"].append(rec) or {**rec, "publication_id": 1})
    monkeypatch.setattr(admin_mod.staging, "merge_staged",
                        lambda sid: state["merged"].append(sid) or 1)
    monkeypatch.setattr(admin_mod.staging, "discard_staged",
                        lambda sid: state["discarded"].append(sid))
    from app.core import security
    from app.main import app

    app.dependency_overrides[security.current_admin] = lambda: {"role": "admin"}
    from fastapi.testclient import TestClient

    state["client"] = TestClient(app)
    yield state
    app.dependency_overrides.clear()
    AccountStore._instance = None


@given(parsers.parse('a faculty submission titled "{title}"'), target_fixture="sub_id")
def submission(ctx, title):
    return AccountStore.instance().create_submission(
        "publication", 7, title, json.dumps({"title": title, "authors": []}))


@when("an admin approves the submission")
def approve(ctx, sub_id):
    assert ctx["client"].post(f"/api/admin/papers/{sub_id}/approve").status_code == 200


@when(parsers.parse('an admin rejects the submission with note "{note}"'))
def reject(ctx, sub_id, note):
    assert ctx["client"].post(f"/api/admin/papers/{sub_id}/reject",
                              json={"note": note}).status_code == 200


@then(parsers.parse('the submission status is "{status}"'))
def has_status(sub_id, status):
    assert AccountStore.instance().get_submission(sub_id)["status"] == status


@then(parsers.parse('the pending queue lists "{title}"'))
def in_queue(ctx, title):
    rows = ctx["client"].get("/api/admin/papers/pending").json()
    assert title in [r["title"] for r in rows]


@then("nothing has been published")
def nothing_published(ctx):
    assert ctx["published"] == [] and ctx["merged"] == []


@then("the record was published")
def was_published(ctx):
    assert len(ctx["published"]) == 1


@then("the staged chunks were merged")
def was_merged(ctx, sub_id):
    assert ctx["merged"] == [sub_id]


@then("the staged chunks were discarded")
def was_discarded(ctx, sub_id):
    assert ctx["discarded"] == [sub_id]


@then(parsers.parse('the faculty member can read the note "{note}"'))
def note_readable(sub_id, note):
    assert AccountStore.instance().get_submission(sub_id)["note"] == note
```

`tests/steps/test_discovery_steps.py`:
```python
from pytest_bdd import given, parsers, scenarios, then

from app.repositories.mock.publications import publication_matches
from scripts.normalize import normalize_name
from tests.test_collaborators import FakeRepo, _r

scenarios("../features/discovery.feature")


@given("a roster where only some researchers share areas or papers",
       target_fixture="repo")
def roster():
    rs = [_r(1, "Alpha", [1, 2]), _r(2, "Beta", [1, 2], campus="Lahore"),
          _r(3, "Gamma", [2]), _r(4, "Delta", [9])]
    ps = [{"authors": [{"researcher_id": 1}, {"researcher_id": 3}],
           "international": False}]
    return FakeRepo(rs, ps)


@then("no suggestion lacks both a shared area and a co-authored paper")
def all_have_signal(repo):
    for c in repo.collaborators(1):
        assert c["shared_count"] > 0 or c["copublications"] > 0


@then(parsers.parse('sorting by "name" returns suggestions in alphabetical order'))
def name_sorted(repo):
    names = [c["full_name"] for c in repo.collaborators(1, sort="name")]
    assert names == sorted(names)


@then("the default order puts a past co-author first")
def coauthor_first(repo):
    assert repo.collaborators(1)[0]["researcher_id"] == 3


@given("publications from several departments, years, and types",
       target_fixture="pubs")
def pubs():
    def p(year, ptype, rid):
        return {"publication_year": year, "publication_type": ptype,
                "authors": [{"researcher_id": rid}]}
    return [p(2019, "conference", 2), p(2020, "journal", 2),
            p(2019, "conference", 1), p(2021, "conference", 2)]


@then(parsers.parse('filtering years 2019-2020 for "Psychology" conference papers '
                    "matches only such records"))
def filtered(pubs):
    dept_of = {1: "Computer Science", 2: "Psychology"}
    hits = [p for p in pubs if publication_matches(
        p, year_from=2019, year_to=2020, department="Psychology",
        publication_type="conference", dept_of=dept_of)]
    assert hits == [pubs[0]]


@given("the seed name normalizer")
def normalizer():
    return None


@then(parsers.parse('"{raw}" is stored as "{clean}"'))
def name_clean(raw, clean):
    assert normalize_name(raw) == clean
```

- [ ] **Step 4: Run the BDD suite, then the whole suite**

Run: `.venv/Scripts/python -m pytest tests/steps -v` → all scenarios pass.
Run: `.venv/Scripts/python -m pytest tests/ -q` → everything green (BDD included in plain collection).
If `from tests.test_collaborators import FakeRepo, _r` fails (helpers module-private), move `FakeRepo`/`_r` into a new `tests/helpers.py` and import from there in BOTH files — do not duplicate them.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/tests/features ResearchSense/backend/tests/steps ResearchSense/backend/tests/helpers.py 2>/dev/null; git add ResearchSense/backend/tests/features ResearchSense/backend/tests/steps
git commit -m "test: Gherkin BDD acceptance scenarios for approval and discovery"
```

---

### Task 4: Frontend gates (vitest + eslint)

**Files:**
- Modify: `ResearchSense/frontend/package.json` (devDeps + `"test"`, `"lint"` scripts)
- Modify: `ResearchSense/frontend/vite.config.ts` (vitest `test` block)
- Modify: `ResearchSense/frontend/tsconfig.json` (exclude test files from build)
- Create: `ResearchSense/frontend/eslint.config.js`
- Create: `ResearchSense/frontend/src/test/setup.ts`
- Create: `ResearchSense/frontend/src/features/analytics/charts.test.tsx`
- Create: `ResearchSense/frontend/src/features/collaboration/NetworkView.test.tsx`
- Create: `ResearchSense/frontend/src/pages/Collaboration.test.tsx`
- Create: `ResearchSense/frontend/src/features/portal/AdminPanel.test.tsx`

**Interfaces:**
- Produces: `npm run lint`, `npm run test` (vitest run), `npm run build` all exit 0 — Tasks 5 and 6 run these exact scripts.

- [ ] **Step 1: Install tooling**

Run (from `ResearchSense/frontend/`):
```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom eslint @eslint/js typescript-eslint eslint-plugin-react-hooks
```
Add scripts to package.json: `"test": "vitest run"`, `"lint": "eslint src"`.

- [ ] **Step 2: Wire vitest and keep tests out of the build**

`vite.config.ts` — add to the exported config (vitest reads it):
```ts
test: {
  environment: "jsdom",
  setupFiles: "./src/test/setup.ts",
  globals: true,
},
```
(If the `defineConfig` import must change to `vitest/config`, change it.)
`src/test/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```
`tsconfig.json` — add `"exclude": ["src/**/*.test.tsx", "src/test"]` (merge with any existing exclude). Verify `npm run build` still succeeds.

- [ ] **Step 3: eslint flat config**

`eslint.config.js`:
```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "vite.config.d.ts", "vite.config.js"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
);
```
Run `npm run lint`; fix trivial violations in src (unused vars etc.); demote-to-warn or scoped-disable anything whose fix would change behavior. Gate ends at zero errors (warnings allowed).

- [ ] **Step 4: Component tests**

`src/features/analytics/charts.test.tsx` (pure-prop components — exact code):
```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DepartmentBars, InternationalTrend } from "./charts";

describe("DepartmentBars", () => {
  it("renders without crashing on empty data", () => {
    const { container } = render(<DepartmentBars data={[]} />);
    expect(container).toBeInTheDocument();
  });

  it("renders at most 10 departments", () => {
    const rows = Array.from({ length: 14 }, (_, i) => ({
      department: `Dept ${i}`, researchers: 1, publications: 14 - i, citations: 0,
    }));
    const { container } = render(<DepartmentBars data={rows} />);
    expect(container.textContent).not.toContain("Dept 13");
  });
});

describe("InternationalTrend", () => {
  it("renders both series names in the legend", () => {
    const { container } = render(
      <InternationalTrend data={[{ year: 2020, international: 2, domestic: 5 }]} />,
    );
    expect(container.textContent?.toLowerCase()).toContain("international");
    expect(container.textContent?.toLowerCase()).toContain("domestic");
  });
});
```
`src/features/collaboration/NetworkView.test.tsx` — read `NetworkView.tsx` first; test with a `CollaborationSuggestion[]` fixture: renders center name; renders at most 8 nodes when given 10 collaborators; a collaborator with `international: true` produces the globe marker (assert on the 🌐 text or the class the implementation uses); an edge for a collaborator with `copublications: 3` has `stroke-width` 4 (1 + min(3,4)).
`src/pages/Collaboration.test.tsx` — mock the api module with `vi.mock("../api/researchers", ...)` (mock `fetchResearchers`, `fetchResearcher`, `fetchCollaborators`), wrap in a fresh `QueryClientProvider`; assert: loader shows before collaborators resolve; after resolution with `[]` the empty-state text shows; with rows, the sort dropdown renders all five options.
`src/features/portal/AdminPanel.test.tsx` — read `AdminPanel.tsx` first; mock its api imports (`vi.mock` on the module that exports `fetchPendingPapers`/`approvePaper`/`rejectPaper`); render with any required props/context read from the component; assert: a pending row's title renders; clicking Approve calls `approvePaper` with the row id; the empty state renders "No papers waiting for review." Adapt mocks to the component's actual imports — do not modify the component to fit the test.

- [ ] **Step 5: Run gates**

Run: `npm run test` → all pass. `npm run lint` → 0 errors. `npm run build` → clean.

- [ ] **Step 6: Commit**

```bash
git add ResearchSense/frontend/package.json ResearchSense/frontend/package-lock.json ResearchSense/frontend/vite.config.ts ResearchSense/frontend/tsconfig.json ResearchSense/frontend/eslint.config.js ResearchSense/frontend/src
git commit -m "test: frontend gauntlet gates (vitest components, eslint, build exclusions)"
```

---

### Task 5: Gauntlet runner

**Files:**
- Create: `ResearchSense/backend/scripts/gauntlet.py`
- Create: `ResearchSense/backend/tests/test_gauntlet.py`

**Interfaces:**
- Consumes: gate commands exactly as produced by Tasks 1–4; `coverage_floor` from `pyproject.toml`.
- Produces: `python -m scripts.gauntlet [--backend-only|--frontend-only]` exit 0 = all gates green; Task 6's CI mirrors these commands.

- [ ] **Step 1: Write the failing test**

`tests/test_gauntlet.py`:
```python
import scripts.gauntlet as g


def test_gate_order_backend_then_frontend():
    names = [gate.name for gate in g.gates()]
    assert names == ["ruff", "ruff-format", "pytest-cov",
                     "eslint", "vitest", "fe-build"]


def test_backend_only_filter():
    names = [gate.name for gate in g.gates(backend_only=True)]
    assert names == ["ruff", "ruff-format", "pytest-cov"]


def test_run_stops_at_first_failure(monkeypatch):
    calls = []

    def fake_exec(gate):
        calls.append(gate.name)
        return gate.name != "ruff-format"  # second gate fails

    monkeypatch.setattr(g, "_exec", fake_exec)
    code = g.run(g.gates())
    assert code == 1
    assert calls == ["ruff", "ruff-format"]


def test_coverage_floor_read_from_pyproject():
    assert isinstance(g.coverage_floor(), int)
    assert g.coverage_floor() >= 0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_gauntlet.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `scripts/gauntlet.py`**

```python
"""One-command quality gauntlet: every gate, fail-fast, same commands as CI.

Run from backend/:  python -m scripts.gauntlet [--backend-only|--frontend-only]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


@dataclass(frozen=True)
class Gate:
    name: str
    cmd: list[str]
    cwd: Path


def coverage_floor() -> int:
    data = tomllib.loads((BACKEND / "pyproject.toml").read_text("utf-8"))
    return int(data["tool"]["gauntlet"]["coverage_floor"])


def _npm() -> str:
    return shutil.which("npm") or "npm"


def gates(backend_only: bool = False, frontend_only: bool = False) -> list[Gate]:
    py = sys.executable
    backend = [
        Gate("ruff", [py, "-m", "ruff", "check", "app", "scripts", "tests"], BACKEND),
        Gate("ruff-format",
             [py, "-m", "ruff", "format", "--check", "app", "scripts", "tests"],
             BACKEND),
        Gate("pytest-cov",
             [py, "-m", "pytest", "tests/", "--cov=app", "--cov=scripts",
              f"--cov-fail-under={coverage_floor()}", "-q"], BACKEND),
    ]
    frontend = [
        Gate("eslint", [_npm(), "run", "lint"], FRONTEND),
        Gate("vitest", [_npm(), "run", "test"], FRONTEND),
        Gate("fe-build", [_npm(), "run", "build"], FRONTEND),
    ]
    if backend_only:
        return backend
    if frontend_only:
        return frontend
    return backend + frontend


def _exec(gate: Gate) -> bool:
    print(f"\n=== gate: {gate.name} ===", flush=True)
    return subprocess.run(gate.cmd, cwd=gate.cwd).returncode == 0


def run(selected: list[Gate]) -> int:
    results: list[tuple[str, bool]] = []
    for gate in selected:
        ok = _exec(gate)
        results.append((gate.name, ok))
        if not ok:
            break
    print("\n=== gauntlet ===")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL':4}  {name}")
    skipped = len(selected) - len(results)
    if skipped:
        print(f"  ({skipped} gate(s) not reached)")
    return 0 if all(ok for _, ok in results) and not skipped else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--backend-only", action="store_true")
    group.add_argument("--frontend-only", action="store_true")
    args = ap.parse_args()
    sys.exit(run(gates(args.backend_only, args.frontend_only)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests green, then one real full run**

Run: `.venv/Scripts/python -m pytest tests/test_gauntlet.py -v` → PASS.
Run: `.venv/Scripts/python -m scripts.gauntlet` → every gate PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/scripts/gauntlet.py ResearchSense/backend/tests/test_gauntlet.py
git commit -m "feat: single-command quality gauntlet runner"
```

---

### Task 6: CI workflow + QA doc

**Files:**
- Create: `.github/workflows/gauntlet.yml` (repo root)
- Create: `docs/QA.md`

**Interfaces:**
- Consumes: the exact gate commands from Tasks 1–5.

- [ ] **Step 1: Write the workflow**

`.github/workflows/gauntlet.yml`:
```yaml
name: gauntlet
on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ResearchSense/backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: ResearchSense/backend/requirements*.txt
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: python -m ruff check app scripts tests
      - run: python -m ruff format --check app scripts tests
      - run: |
          FLOOR=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['gauntlet']['coverage_floor'])")
          python -m pytest tests/ --cov=app --cov=scripts --cov-fail-under=$FLOOR -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ResearchSense/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: ResearchSense/frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run test
      - run: npm run build
```
Note: backend CI installs `requirements.txt` too — it must resolve on Linux; if a Windows-only pin breaks it, mark that step's failure in the report rather than editing requirements silently.

- [ ] **Step 2: Write docs/QA.md**

```markdown
# QA — The Quality Gauntlet

Every change, human or agent, passes the gauntlet before merge.

## Run it

    cd ResearchSense/backend
    python -m scripts.gauntlet            # everything
    python -m scripts.gauntlet --backend-only
    python -m scripts.gauntlet --frontend-only

CI (`.github/workflows/gauntlet.yml`) runs the identical commands on every
push and pull request. A red gate blocks the merge.

## Gates

| Gate | Command | Blocks on |
|---|---|---|
| ruff | `ruff check app scripts tests` | any lint finding |
| ruff-format | `ruff format --check ...` | formatting drift |
| pytest-cov | `pytest tests/ --cov=app --cov=scripts --cov-fail-under=<floor>` | test failure or coverage below floor |
| eslint | `npm run lint` | any error (warnings allowed) |
| vitest | `npm run test` | any component test failure |
| fe-build | `npm run build` | type error or build failure |

## The ratchet rule

The coverage floor lives in `ResearchSense/backend/pyproject.toml` under
`[tool.gauntlet] coverage_floor`. It may only ever increase. Raising it is
encouraged whenever real tests push coverage up; lowering it, disabling a
lint rule, or adding a per-file-ignore requires an explicit justification in
the commit message.

## Adding a BDD scenario

1. Add a `Scenario:` to `tests/features/*.feature` (plain Gherkin).
2. Bind any new steps in `tests/steps/test_*_steps.py` with pytest-bdd
   (`@given/@when/@then`, `parsers.parse` for arguments).
3. Scenarios use TestClient + tmp-path SQLite + monkeypatched staging —
   never live data files or the network.
```

- [ ] **Step 3: Verify workflow syntax + final full gauntlet**

Run: `cd ResearchSense/backend && .venv/Scripts/python -c "import yaml,sys;yaml.safe_load(open('../../.github/workflows/gauntlet.yml'));print('yaml ok')"` (pyyaml is available transitively; if not, `pip install pyyaml`).
Run: `.venv/Scripts/python -m scripts.gauntlet` → all gates PASS.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/gauntlet.yml docs/QA.md
git commit -m "chore: CI gauntlet workflow + QA contract"
```

- [ ] **Step 5: CI verification (push)**

If pushing is authorized at execution time: `git push -u origin supervisor-feedback-upgrade` and confirm the `gauntlet` workflow runs green on GitHub. If not authorized, record "CI verification pending push" in the task report — do not push without the user's go-ahead.
