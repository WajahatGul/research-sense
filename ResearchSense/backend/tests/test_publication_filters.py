from app.repositories.mock.publications import effective_date, publication_matches


def _p(year=2020, ptype="journal", authors=(1,), date=None):
    return {
        "publication_year": year,
        "publication_type": ptype,
        "publication_date": date,
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


# --- effective_date ---


def test_effective_date_well_formed_date_passes_through():
    assert effective_date(_p(date="2021-05-03")) == "2021-05-03"


def test_effective_date_malformed_date_falls_back_to_year():
    assert effective_date(_p(year=2020, date="2020-13-99")) == "2020-01-01"


def test_effective_date_non_iso_date_falls_back_to_year():
    assert effective_date(_p(year=2020, date="2020")) == "2020-01-01"


def test_effective_date_missing_date_falls_back_to_year():
    assert effective_date(_p(year=2020, date=None)) == "2020-01-01"


def test_effective_date_neither_gives_epoch_zero():
    assert effective_date(_p(year=0, date=None)) == "0000-01-01"


# --- date range filtering ---


def test_date_range_inclusive_both_ends():
    assert publication_matches(
        _p(date="2020-06-15"),
        date_from="2020-06-15",
        date_to="2020-06-15",
        dept_of=DEPT_OF,
    )
    assert not publication_matches(
        _p(date="2020-06-14"),
        date_from="2020-06-15",
        date_to="2020-06-15",
        dept_of=DEPT_OF,
    )
    assert not publication_matches(
        _p(date="2020-06-16"),
        date_from="2020-06-15",
        date_to="2020-06-15",
        dept_of=DEPT_OF,
    )


def test_date_range_open_ended():
    assert publication_matches(
        _p(date="2024-01-01"), date_from="2020-01-01", dept_of=DEPT_OF
    )
    assert publication_matches(
        _p(date="2012-01-01"), date_to="2015-01-01", dept_of=DEPT_OF
    )
    assert not publication_matches(
        _p(date="2010-01-01"), date_from="2020-01-01", dept_of=DEPT_OF
    )


def test_year_only_record_included_by_range_spanning_its_jan_first():
    assert publication_matches(
        _p(year=2020, date=None),
        date_from="2019-06-01",
        date_to="2020-06-01",
        dept_of=DEPT_OF,
    )


def test_year_only_record_excluded_by_range_starting_mid_year():
    assert not publication_matches(
        _p(year=2020, date=None),
        date_from="2020-06-01",
        date_to="2020-12-31",
        dept_of=DEPT_OF,
    )


def test_year_from_and_date_from_both_applied():
    # Passes date_from but fails year_from -> excluded.
    assert not publication_matches(
        _p(year=2019, date="2019-12-31"),
        year_from=2020,
        date_from="2019-01-01",
        dept_of=DEPT_OF,
    )
    # Passes both -> included.
    assert publication_matches(
        _p(year=2020, date="2020-03-01"),
        year_from=2020,
        date_from="2019-01-01",
        dept_of=DEPT_OF,
    )
