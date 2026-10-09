"""Researchers correct their own records; administrators decide; decisions last.

Runs against copies of the data files and a temporary database: approving a
correction rewrites the data, and a test must never touch the real files.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core.security import create_token, hash_password
from app.repositories import loader
from app.repositories.accounts import AccountStore
from app.services import identity_service

ARIF = 8  # Arif Ur Rahman
ARIF_ORCID = "0000-0001-8239-2033"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in ("researchers", "publications", "topics"):
        shutil.copy(loader.DATA_DIR / f"{name}.json", data / f"{name}.json")
    monkeypatch.setattr(loader, "DATA_DIR", data)
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    loader.clear_cache()
    identity_service._candidate_cache.clear()
    AccountStore.instance().create_account(
        ARIF_ORCID, ARIF, hash_password("pw-12345678")
    )
    from app.main import app

    client = TestClient(app)
    researcher = {"Authorization": f"Bearer {create_token(ARIF_ORCID, 'researcher')}"}
    admin = {"Authorization": f"Bearer {create_token('admin', 'admin')}"}
    yield client, researcher, admin, data
    AccountStore._instance = None
    loader.clear_cache()
    identity_service._candidate_cache.clear()


def _papers_of(rid):
    return [
        p
        for p in loader.load("publications")
        if any(a.get("researcher_id") == rid for a in p["authors"])
    ]


def test_not_mine_waits_for_review_then_leaves_the_profile(env):
    client, me, admin, _ = env
    paper = _papers_of(ARIF)[0]
    r = client.post(
        "/api/corrections/not-mine",
        headers=me,
        json={"publication_id": paper["publication_id"], "note": "Not my field"},
    )
    assert r.json()["status"] == "pending"
    assert paper["publication_id"] in {p["publication_id"] for p in _papers_of(ARIF)}

    [pending] = client.get("/api/admin/corrections", headers=admin).json()
    assert pending["paper_title"] == paper["title"]
    client.post(f"/api/admin/corrections/{pending['id']}/approve", headers=admin)

    assert paper["publication_id"] not in {
        p["publication_id"] for p in _papers_of(ARIF)
    }
    mine = client.get("/api/corrections/mine", headers=me).json()["corrections"]
    assert mine[0]["status"] == "approved"


def test_a_researcher_can_only_disown_their_own_papers(env):
    client, me, _, _ = env
    other = next(
        p
        for p in loader.load("publications")
        if p["authors"] and all(a.get("researcher_id") != ARIF for a in p["authors"])
    )
    r = client.post(
        "/api/corrections/not-mine",
        headers=me,
        json={"publication_id": other["publication_id"]},
    )
    assert r.status_code == 404


def test_is_this_also_you_suggestions_and_dismissal(env):
    client, me, _, _ = env
    suggestions = client.get("/api/corrections/mine", headers=me).json()["suggestions"]
    rehman = next(s for s in suggestions if s["other_name"] == "Arif Ur Rehman")
    client.post(
        "/api/corrections/not-me",
        headers=me,
        json={"openalex_id": rehman["openalex_id"]},
    )
    after = client.get("/api/corrections/mine", headers=me).json()["suggestions"]
    assert rehman["openalex_id"] not in {s["openalex_id"] for s in after}


def test_same_person_folds_the_record_in_after_approval(env):
    client, me, admin, _ = env
    s = client.get("/api/corrections/mine", headers=me).json()["suggestions"][0]
    before = len(_papers_of(ARIF))
    client.post(
        "/api/corrections/same-person",
        headers=me,
        json={"openalex_id": s["openalex_id"]},
    )
    [pending] = client.get("/api/admin/corrections", headers=admin).json()
    assert pending["kind"] == "same_person" and pending["evidence"]
    client.post(f"/api/admin/corrections/{pending['id']}/approve", headers=admin)
    assert len(_papers_of(ARIF)) == before + s["paper_count"]
    assert not any(
        r.get("openalex_id") == s["openalex_id"] for r in loader.load("researchers")
    )


def test_decisions_survive_a_refresh(env):
    """A refresh rebuilds the data from the source; the decision is re-applied."""
    client, me, admin, data = env
    original = (data / "publications.json").read_text("utf-8")
    paper = _papers_of(ARIF)[0]
    client.post(
        "/api/corrections/not-mine",
        headers=me,
        json={"publication_id": paper["publication_id"]},
    )
    [pending] = client.get("/api/admin/corrections", headers=admin).json()
    client.post(f"/api/admin/corrections/{pending['id']}/approve", headers=admin)

    # Simulate the refresh: fresh data from the source, then decisions applied.
    (data / "publications.json").write_text(original, "utf-8")
    loader.clear_cache()
    assert paper["publication_id"] in {p["publication_id"] for p in _papers_of(ARIF)}
    identity_service.apply_and_save()
    assert paper["publication_id"] not in {
        p["publication_id"] for p in _papers_of(ARIF)
    }


def test_admin_decides_on_a_system_suggestion(env):
    client, _, admin, _ = env
    first = client.get("/api/admin/corrections/candidates", headers=admin).json()[0]
    client.post(
        "/api/admin/corrections/candidates/decide",
        headers=admin,
        json={
            "researcher_id": first["researcher_id"],
            "openalex_id": first["openalex_id"],
            "same": False,
        },
    )
    after = client.get("/api/admin/corrections/candidates", headers=admin).json()
    assert (first["researcher_id"], first["openalex_id"]) not in {
        (c["researcher_id"], c["openalex_id"]) for c in after
    }


def test_only_admins_see_the_queue(env):
    client, me, _, _ = env
    assert client.get("/api/admin/corrections", headers=me).status_code in (401, 403)
