"""A refresh that fails, or produces data unfit to serve, leaves the site as it was."""

import json

import pytest


@pytest.fixture
def refresh(monkeypatch, tmp_path):
    import app.repositories.accounts as accounts_mod
    from app.repositories.accounts import AccountStore
    from app.services import identity_service, refresh_service
    from scripts import (
        build_index,
        classify_topics,
        fetch_publications,
        merge_author_variants,
        merge_duplicate_publications,
        unlink_misattributed,
    )

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(AccountStore, "_instance", None)
    monkeypatch.setattr(fetch_publications, "DATA_DIR", data)
    monkeypatch.setattr(refresh_service, "_reload", lambda: None)

    people = [{"researcher_id": i} for i in range(1, 11)]
    papers = [{"publication_id": i} for i in range(1, 11)]
    (data / "researchers.json").write_text(json.dumps(people))
    (data / "publications.json").write_text(json.dumps(papers))
    (data / "topics.json").write_text('[{"topic_id": 1}]')
    (data / "publication_duplicates.json").write_text("[]")
    original = {n: (data / n).read_text() for n in ("researchers.json", "publications.json", "topics.json")}

    steps = {"fetch": lambda: None, "fields": lambda: None}
    monkeypatch.setattr(fetch_publications, "main", lambda: steps["fetch"]())
    monkeypatch.setattr(merge_author_variants, "main", lambda write: None)
    monkeypatch.setattr(unlink_misattributed, "main", lambda write: None)
    monkeypatch.setattr(merge_duplicate_publications, "main", lambda write: None)
    monkeypatch.setattr(classify_topics, "main", lambda write: steps["fields"]())
    monkeypatch.setattr(identity_service, "apply_and_save", lambda: None)
    monkeypatch.setattr(build_index, "rebuild_preserving_fulltext", lambda: None)

    def unchanged():
        return all((data / n).read_text() == text for n, text in original.items())

    return refresh_service, data, steps, unchanged


def last_status():
    from app.repositories.accounts import AccountStore

    with AccountStore.instance()._connect() as con:
        rows = con.execute(
            "SELECT status FROM refresh_log ORDER BY id DESC LIMIT 1"
        ).fetchall()
    return rows[0][0]


def test_a_good_refresh_is_kept_and_leaves_no_copy(refresh):
    service, data, steps, _ = refresh

    def fetch():
        papers = [{"publication_id": i} for i in range(1, 13)]
        (data / "publications.json").write_text(json.dumps(papers))

    steps["fetch"] = fetch
    assert service.run_refresh() == "ok"
    assert len(json.loads((data / "publications.json").read_text())) == 12
    assert not (data / ".refresh-snapshot").exists()


def test_a_crash_part_way_puts_every_file_back(refresh):
    service, data, steps, unchanged = refresh

    def fetch():
        (data / "publications.json").write_text("[]")  # half-written
        (data / "publication_duplicates.json").unlink()

    def fields():
        raise RuntimeError("out of memory")

    steps["fetch"], steps["fields"] = fetch, fields
    result = service.run_refresh()
    assert "out of memory" in result and "restored" in result
    assert unchanged()
    assert (data / "publication_duplicates.json").exists()
    assert not (data / ".refresh-snapshot").exists()
    assert "restored" in last_status()


def test_data_that_lost_most_papers_is_not_served(refresh):
    service, data, steps, unchanged = refresh
    steps["fetch"] = lambda: (data / "publications.json").write_text('[{"publication_id": 1}]')
    result = service.run_refresh()
    assert "papers fell from 10 to 1" in result
    assert unchanged()


def test_repeated_paper_numbers_are_not_served(refresh):
    service, data, steps, unchanged = refresh
    papers = [{"publication_id": i % 9} for i in range(10)]
    steps["fetch"] = lambda: (data / "publications.json").write_text(json.dumps(papers))
    assert "repeated" in service.run_refresh()
    assert unchanged()


def test_an_index_out_of_step_with_its_passages_is_not_served(refresh):
    import numpy as np

    service, data, steps, unchanged = refresh

    def fetch():
        (data / "rag_chunks.json").write_text('[{"id": 1}, {"id": 2}]')
        np.savez(data / "rag_index.npz", vectors=np.zeros((1, 4)))

    steps["fetch"] = fetch
    assert "1 vectors for 2 passages" in service.run_refresh()
    assert unchanged()
    # Files the refresh created are removed again, not left beside the old data.
    assert not (data / "rag_chunks.json").exists()
