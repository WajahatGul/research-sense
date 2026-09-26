"""One work, one record: preprints and second DOIs fold into the paper."""

from collections import Counter

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import loader
from scripts.merge_duplicate_publications import find_duplicates, title_key

client = TestClient(app)


def _paper(pid, title, venue, doi, cites=0, authors=("Ali Mirza",)):
    return {"publication_id": pid, "title": title, "journal_name": venue, "doi": doi,
            "citation_count": cites, "publication_year": 2020,
            "authors": [{"researcher_id": None, "full_name": a} for a in authors]}


def test_the_journal_version_is_kept_over_the_preprint():
    rows = [
        _paper(1, "A Study of Things in Detail", "SSRN Electronic Journal", "10.2139/ssrn.1", 7),
        _paper(2, "A study of things in detail.", "IEEE Access", "10.1109/x", 3),
    ]
    assert [(m["removed_id"], m["kept_id"]) for m in find_duplicates(rows)] == [(1, 2)]


def test_same_title_by_different_people_is_not_merged():
    rows = [
        _paper(1, "A Study of Things in Detail", "IEEE Access", "10.1", authors=("Ali Mirza",)),
        _paper(2, "A Study of Things in Detail", "Sensors", "10.2", authors=("Sara Khan",)),
    ]
    assert find_duplicates(rows) == []


def test_the_corpus_holds_each_work_once():
    assert find_duplicates(loader.load("publications")) == []


def test_a_merged_paper_lists_its_other_versions():
    paper = client.get("/api/publications/76").json()
    venues = [v["journal_name"] for v in paper["versions"]]
    assert "SSRN Electronic Journal" in venues


def test_an_old_link_to_a_folded_copy_still_opens_the_paper():
    r = client.get("/api/publications/669")  # the SSRN copy of paper 76
    assert r.status_code == 200
    assert r.json()["publication_id"] == 76


def test_an_author_list_no_longer_repeats_a_paper():
    rows = loader.load("publications")
    for rid in (106, 164, 235):
        titles = [title_key(p["title"]) for p in rows
                  if any(a.get("researcher_id") == rid for a in p["authors"])]
        repeated = [t for t, n in Counter(titles).items() if n > 1 and len(t) >= 16]
        assert repeated == [], rid


def test_a_refresh_cleans_the_new_data_before_indexing(monkeypatch, tmp_path):
    from app.services import refresh_service
    from scripts import (
        build_index,
        classify_topics,
        fetch_publications,
        merge_author_variants,
        merge_duplicate_publications,
        unlink_misattributed,
    )

    calls = []
    monkeypatch.setattr(fetch_publications, "DATA_DIR", tmp_path)
    (tmp_path / "publication_duplicates.json").write_text("[]")
    monkeypatch.setattr(fetch_publications, "main", lambda: calls.append("fetch"))
    monkeypatch.setattr(merge_author_variants, "main", lambda write: calls.append("people"))
    monkeypatch.setattr(unlink_misattributed, "main", lambda write: calls.append("unlink"))
    monkeypatch.setattr(merge_duplicate_publications, "main", lambda write: calls.append("dupes"))
    monkeypatch.setattr(classify_topics, "main", lambda write: calls.append("fields"))
    monkeypatch.setattr(build_index, "rebuild_preserving_fulltext", lambda: calls.append("index"))

    assert refresh_service.run_refresh() == "ok"
    assert calls == ["fetch", "people", "unlink", "dupes", "fields", "index"]
    assert not (tmp_path / "publication_duplicates.json").exists()
