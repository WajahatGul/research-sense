"""A researcher can invite the co-authors who have not claimed a profile."""

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core.deps import get_auth_service
from app.core.security import create_token, hash_password
from app.repositories import loader
from app.repositories.accounts import AccountStore

ARIF, ORCID = 8, "0000-0001-8239-2033"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    get_auth_service.cache_clear()
    AccountStore.instance().create_account(ORCID, ARIF, hash_password("pw-12345678"))
    from app.main import app

    yield TestClient(app), {"Authorization": f"Bearer {create_token(ORCID, 'researcher')}"}
    AccountStore._instance = None


def test_lists_directory_coauthors_most_joint_papers_first(client):
    c, me = client
    rows = c.get("/api/invitations/coauthors", headers=me).json()["coauthors"]
    assert rows, "Arif Ur Rahman has directory co-authors"
    counts = [r["joint_papers"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    people = {r["researcher_id"]: r for r in loader.load("researchers")}
    assert all(not loader.is_extended(people[r["researcher_id"]]) for r in rows)
    assert rows[0]["claim_link"].endswith(f"/portal?claim={rows[0]['researcher_id']}")


def test_people_who_claimed_or_are_waiting_are_left_out(client):
    c, me = client
    first = c.get("/api/invitations/coauthors", headers=me).json()["coauthors"][0]
    AccountStore.instance().create_claim("0000-0002-1825-0097", first["researcher_id"], "x", "{}")
    after = c.get("/api/invitations/coauthors", headers=me).json()["coauthors"]
    assert first["researcher_id"] not in {r["researcher_id"] for r in after}


def test_signed_in_researchers_only(client):
    c, _ = client
    assert c.get("/api/invitations/coauthors").status_code == 401
