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
