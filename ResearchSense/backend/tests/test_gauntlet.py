import scripts.gauntlet as g


def test_gate_order_backend_then_frontend():
    names = [gate.name for gate in g.gates()]
    assert names == [
        "ruff",
        "ruff-format",
        "pytest-cov",
        "eslint",
        "vitest",
        "fe-build",
    ]


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
