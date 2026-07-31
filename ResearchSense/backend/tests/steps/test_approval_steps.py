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
        admin_mod.submission_service,
        "publish_record",
        lambda rec: state["published"].append(rec) or {**rec, "publication_id": 1},
    )
    monkeypatch.setattr(
        admin_mod.staging, "merge_staged", lambda sid: state["merged"].append(sid) or 1
    )
    monkeypatch.setattr(
        admin_mod.staging, "discard_staged", lambda sid: state["discarded"].append(sid)
    )
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
        "publication", 7, title, json.dumps({"title": title, "authors": []})
    )


@when("an admin approves the submission")
def approve(ctx, sub_id):
    assert ctx["client"].post(f"/api/admin/papers/{sub_id}/approve").status_code == 200


@when(parsers.parse('an admin rejects the submission with note "{note}"'))
def reject(ctx, sub_id, note):
    assert (
        ctx["client"]
        .post(f"/api/admin/papers/{sub_id}/reject", json={"note": note})
        .status_code
        == 200
    )


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
