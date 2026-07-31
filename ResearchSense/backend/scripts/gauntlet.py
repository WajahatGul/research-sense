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
        Gate(
            "ruff-format",
            [py, "-m", "ruff", "format", "--check", "app", "scripts", "tests"],
            BACKEND,
        ),
        Gate(
            "pytest-cov",
            [
                py,
                "-m",
                "pytest",
                "tests/",
                "--cov=app",
                "--cov=scripts",
                f"--cov-fail-under={coverage_floor()}",
                "-q",
            ],
            BACKEND,
        ),
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
