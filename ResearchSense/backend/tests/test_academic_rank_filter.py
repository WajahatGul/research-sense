"""Tests for academic_rank wiring in the mock researcher repository/router:
academic_ranks() ordering and the dual-match designation filter (Task 3)."""

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.mock.researchers import MockResearcherRepository


def _r(rid, name, designation, academic_rank, department="CS", campus="Karachi"):
    return {
        "researcher_id": rid,
        "full_name": name,
        "designation": designation,
        "academic_rank": academic_rank,
        "department": department,
        "campus": campus,
        "topics": [],
    }


class FakeRepo(MockResearcherRepository):
    def __init__(self, researchers):
        self._rs = researchers

    def _all(self):
        return self._rs


class TestAcademicRanks:
    def test_ordering_follows_canonical_priority_not_alphabetical(self):
        repo = FakeRepo(
            [
                _r(1, "A", "Professor", "Professor"),
                _r(2, "B", "Assistant Professor", "Assistant Professor"),
                _r(3, "C", "Departmental Coordinator", "Other"),
                _r(4, "D", "Senior Lecturer", "Senior Lecturer"),
            ]
        )
        ranks = repo.academic_ranks()
        # "Assistant Professor" must come before "Professor" (canonical
        # order), and "Other" must be last -- not alphabetical.
        assert ranks == ["Senior Lecturer", "Assistant Professor", "Professor", "Other"]

    def test_only_present_ranks_returned(self):
        repo = FakeRepo(
            [
                _r(1, "A", "Lecturer", "Lecturer"),
            ]
        )
        assert repo.academic_ranks() == ["Lecturer"]

    def test_empty_academic_rank_excluded(self):
        repo = FakeRepo(
            [
                _r(1, "A", "", ""),
                _r(2, "B", "Professor", "Professor"),
            ]
        )
        assert repo.academic_ranks() == ["Professor"]


class TestDualMatchDesignationFilter:
    def test_filters_by_full_designation_still_works(self):
        hod = "Associate Professor / HoD HR & Management"
        repo = FakeRepo(
            [
                _r(1, "A", hod, "Associate Professor"),
                _r(2, "B", "Lecturer", "Lecturer"),
            ]
        )
        rows = repo.list(designation=hod)
        assert [r.researcher_id for r in rows] == [1]

    def test_filters_by_academic_rank_returns_compound_titles(self):
        hod = "Associate Professor / HoD HR & Management"
        dean = "Dean & Principal / Associate Professor"
        repo = FakeRepo(
            [
                _r(1, "A", hod, "Associate Professor"),
                _r(2, "B", dean, "Associate Professor"),
                _r(3, "C", "Lecturer", "Lecturer"),
            ]
        )
        rows = repo.list(designation="Associate Professor")
        assert sorted(r.researcher_id for r in rows) == [1, 2]


class TestAcademicRanksEndpoint:
    def test_endpoint_returns_list(self):
        client = TestClient(app)
        resp = client.get("/api/researchers/academic-ranks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_endpoint_not_shadowed_by_researcher_id_route(self):
        client = TestClient(app)
        resp = client.get("/api/researchers/academic-ranks")
        # A 422/404 here would mean the {researcher_id} route swallowed it.
        assert resp.status_code == 200
