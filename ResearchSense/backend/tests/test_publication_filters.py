from app.repositories.mock.publications import publication_matches


def _p(year=2020, ptype="journal", authors=(1,)):
    return {
        "publication_year": year,
        "publication_type": ptype,
        "authors": [{"researcher_id": a} for a in authors],
    }


DEPT_OF = {1: "Computer Science", 2: "Psychology"}


def test_year_range_inclusive():
    assert publication_matches(
        _p(year=2020), year_from=2019, year_to=2020, dept_of=DEPT_OF
    )
    assert not publication_matches(
        _p(year=2018), year_from=2019, year_to=2020, dept_of=DEPT_OF
    )


def test_open_ended_ranges():
    assert publication_matches(_p(year=2024), year_from=2020, dept_of=DEPT_OF)
    assert publication_matches(_p(year=2012), year_to=2015, dept_of=DEPT_OF)


def test_department_matches_any_linked_author():
    assert publication_matches(
        _p(authors=(1, 2)), department="Psychology", dept_of=DEPT_OF
    )
    assert not publication_matches(
        _p(authors=(1,)), department="Psychology", dept_of=DEPT_OF
    )


def test_publication_type_filter():
    assert publication_matches(
        _p(ptype="conference"), publication_type="conference", dept_of=DEPT_OF
    )
    assert not publication_matches(
        _p(ptype="journal"), publication_type="conference", dept_of=DEPT_OF
    )


def test_no_filters_matches_everything():
    assert publication_matches(_p(), dept_of=DEPT_OF)
