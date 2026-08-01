from pytest_bdd import given, parsers, scenarios, then

from app.repositories.mock.publications import publication_matches
from scripts.normalize import normalize_name
from tests.test_collaborators import FakeRepo, _r

scenarios("../features/discovery.feature")


@given(
    "a roster where only some researchers share areas or papers", target_fixture="repo"
)
def roster():
    rs = [
        _r(1, "Alpha", [1, 2]),
        _r(2, "Beta", [1, 2], campus="Lahore"),
        _r(3, "Gamma", [2]),
        _r(4, "Delta", [9]),
    ]
    ps = [
        {
            "authors": [{"researcher_id": 1}, {"researcher_id": 3}],
            "international": False,
        }
    ]
    return FakeRepo(rs, ps)


@then("no suggestion lacks both a shared area and a co-authored paper")
def all_have_signal(repo):
    for c in repo.collaborators(1):
        assert c["shared_count"] > 0 or c["copublications"] > 0


@then(parsers.parse('sorting by "name" returns suggestions in alphabetical order'))
def name_sorted(repo):
    names = [c["full_name"] for c in repo.collaborators(1, sort="name")]
    assert names == sorted(names)


@then("the default order puts a past co-author first")
def coauthor_first(repo):
    assert repo.collaborators(1)[0]["researcher_id"] == 3


@given("publications from several departments, years, and types", target_fixture="pubs")
def pubs():
    def p(year, ptype, rid):
        return {
            "publication_year": year,
            "publication_type": ptype,
            "authors": [{"researcher_id": rid}],
        }

    return [
        p(2019, "conference", 2),
        p(2020, "journal", 2),
        p(2019, "conference", 1),
        p(2021, "conference", 2),
    ]


@then(
    parsers.parse(
        'filtering years 2019-2020 for "Psychology" conference papers '
        "matches only such records"
    )
)
def filtered(pubs):
    dept_of = {1: "Computer Science", 2: "Psychology"}
    hits = [
        p
        for p in pubs
        if publication_matches(
            p,
            year_from=2019,
            year_to=2020,
            department="Psychology",
            publication_type="conference",
            dept_of=dept_of,
        )
    ]
    assert hits == [pubs[0]]


@given("the seed name normalizer")
def normalizer():
    return None


@then(parsers.parse('"{raw}" is stored as "{clean}"'))
def name_clean(raw, clean):
    assert normalize_name(raw) == clean
