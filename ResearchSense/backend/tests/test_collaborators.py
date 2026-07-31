import pytest

from app.repositories.mock.researchers import MockResearcherRepository, score_of


def _r(rid, name, topics, campus="Karachi", intl=None):
    return {"researcher_id": rid, "full_name": name, "designation": "Lecturer",
            "department": "CS", "campus": campus,
            "topics": [{"topic_id": t, "topic_name": f"T{t}"} for t in topics],
            "international_collaborations": intl or []}


class FakeRepo(MockResearcherRepository):
    def __init__(self, researchers, publications):
        self._rs, self._ps = researchers, publications
    def _all(self):
        return self._rs
    def _pubs(self):
        return self._ps


@pytest.fixture()
def repo():
    rs = [_r(1, "Alpha", [1, 2]),
          _r(2, "Beta", [1, 2], campus="Lahore"),
          _r(3, "Gamma", [2]),
          _r(4, "Delta", [9]),           # no shared signal with Alpha
          _r(5, "Echo", [1], intl=[{"institution": "MIT", "country": "US"}])]
    ps = [{"authors": [{"researcher_id": 1}, {"researcher_id": 3}],
           "international": False}]
    return FakeRepo(rs, ps)


def test_no_signal_candidates_are_dropped(repo):
    ids = [c["researcher_id"] for c in repo.collaborators(1)]
    assert 4 not in ids


def test_coauthor_outranks_shared_areas_by_default(repo):
    ids = [c["researcher_id"] for c in repo.collaborators(1)]
    assert ids[0] == 3  # past co-author first


def test_rare_shared_area_scores_higher_than_common():
    # Topic 5 is shared by 2 people; topic 1 by four -> rarer wins.
    rs = [_r(1, "A", [1, 5]), _r(2, "B", [1]), _r(3, "C", [1]),
          _r(4, "D", [1]), _r(5, "E", [5])]
    repo = FakeRepo(rs, [])
    freq = {1: 4, 5: 2}
    assert score_of(copub=0, shared_ids={5}, topic_freq=freq) > \
           score_of(copub=0, shared_ids={1}, topic_freq=freq)


def test_sort_by_name(repo):
    names = [c["full_name"] for c in repo.collaborators(1, sort="name")]
    assert names == sorted(names)


def test_sort_by_coauthored(repo):
    rows = repo.collaborators(1, sort="coauthored")
    assert rows[0]["researcher_id"] == 3


def test_international_flag_from_candidate_collabs(repo):
    echo = next(c for c in repo.collaborators(1)
                if c["researcher_id"] == 5)
    assert echo["international"] is True
