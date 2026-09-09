"""Self-service institution workspaces.

The critical property is isolation: a signed-up institution must never see the
bundled demo corpus, and writing into a workspace must never touch it.
"""

from __future__ import annotations

import pytest

from app.repositories import loader
from app.services import cv_service, workspace_service

WS = "test-institution"


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """A throwaway workspace on disk, with the demo corpus left alone."""
    monkeypatch.setattr(loader, "WORKSPACES_DIR", tmp_path / "workspaces")
    loader.clear_cache()
    loader.save(
        "researchers",
        [
            {
                "researcher_id": 1,
                "full_name": "Sara Ahmed",
                "designation": "",
                "academic_rank": "",
                "department": "Computer Science",
                "campus": "Main campus",
                "publication_count": 0,
                "citation_count": 0,
                "research_areas": [],
                "topics": [],
            }
        ],
        WS,
    )
    loader.save("publications", [], WS)
    loader.save("topics", [], WS)
    yield WS
    loader.set_workspace(None)
    loader.clear_cache()


def test_workspace_is_isolated_from_the_demo_corpus():
    loader.set_workspace(WS)
    assert len(loader.load("researchers")) == 1
    assert loader.load("publications") == []

    # Switching back to the default shows the bundled corpus, untouched.
    loader.set_workspace(None)
    assert len(loader.load("researchers")) > 1


def test_apply_profile_saves_areas_and_derives_topics():
    workspace_service.apply_profile(
        WS,
        1,
        {
            "full_name": "Dr Sara Ahmed",
            "designation": "Associate Professor",
            "department": "Computer Science",
            "education": "PhD, Manchester",
            "profile_bio": "Works on federated learning.",
            "research_areas": ["Federated Learning", "Medical Imaging"],
        },
    )
    loader.set_workspace(WS)
    owner = loader.load("researchers")[0]
    assert owner["full_name"] == "Dr Sara Ahmed"
    assert owner["designation"] == "Associate Professor"
    assert owner["research_areas"] == ["Federated Learning", "Medical Imaging"]
    assert [t["topic_name"] for t in loader.load("topics")] == [
        "Federated Learning",
        "Medical Imaging",
    ]


def test_add_publications_dedupes_and_updates_counts():
    workspace_service.apply_profile(
        WS, 1, {"full_name": "Sara", "research_areas": ["Federated Learning"]}
    )
    items = [
        {"title": "Paper One", "publication_year": 2023, "journal_name": "IEEE"},
        {"title": "Paper Two", "publication_year": 2021, "doi": "10.1/xyz"},
    ]
    assert workspace_service.add_publications(WS, 1, items) == 2

    # Same title and same DOI are both rejected on a second pass.
    assert workspace_service.add_publications(WS, 1, items) == 0

    loader.set_workspace(WS)
    pubs = loader.load("publications")
    assert len(pubs) == 2
    assert loader.load("researchers")[0]["publication_count"] == 2
    # The author is linked so the paper shows on the profile.
    assert pubs[0]["authors"][0]["researcher_id"] == 1


def test_publications_without_a_title_are_skipped():
    assert workspace_service.add_publications(WS, 1, [{"title": "   "}]) == 0


def test_cv_parse_returns_the_full_shape_when_the_model_is_unavailable(monkeypatch):
    """The review form must always render, even with no model configured."""
    monkeypatch.setattr(cv_service, "available", lambda: False)
    draft = cv_service.parse_cv("Some CV text that is long enough to pass.")
    assert draft["publications"] == []
    assert draft["research_areas"] == []
    for key in ("full_name", "designation", "department", "education"):
        assert key in draft


def test_cv_publication_rows_are_cleaned():
    rows = cv_service._coerce_publications(
        [
            {"title": "Good", "publication_year": "2022", "journal_name": "J"},
            {"title": "", "publication_year": 2020},  # dropped: no title
            {"title": "Bad year", "publication_year": 99},  # year cleared
            "not a dict",  # ignored
        ]
    )
    assert [r["title"] for r in rows] == ["Good", "Bad year"]
    assert rows[0]["publication_year"] == 2022
    assert rows[1]["publication_year"] is None
