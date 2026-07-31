from scripts.fetch_sources import (
    country_from_affiliation,
    dedupe_key,
    normalize_crossref_item,
    normalize_s2_paper,
)


def test_dedupe_prefers_doi():
    assert dedupe_key("10.1/ABC", "Any Title", 2020) == "doi:10.1/abc"


def test_dedupe_falls_back_to_title_year():
    assert dedupe_key(None, "A Study: of Things!", 2021) == "ty:astudyofthings:2021"


def test_country_from_affiliation_matches_country_name():
    assert country_from_affiliation("MIT, Cambridge, United States") == "US"
    assert country_from_affiliation("Bahria University, Islamabad, Pakistan") == "PK"


def test_country_from_affiliation_unknown_is_none():
    assert country_from_affiliation("Some Lab") is None


def test_normalize_s2_paper_shapes_record():
    raw = {
        "title": "T",
        "year": 2022,
        "externalIds": {"DOI": "10.2/x"},
        "venue": "VenueX",
        "citationCount": 3,
        "fieldsOfStudy": ["Biology"],
        "authors": [{"name": "A B", "affiliations": ["Uni, Pakistan"]}],
        "publicationTypes": ["JournalArticle"],
    }
    rec = normalize_s2_paper(raw)
    assert rec["doi"] == "10.2/x" and rec["publication_year"] == 2022
    assert rec["topic_names"] == ["Biology"]
    assert rec["authors"][0]["affiliation"] == "Uni, Pakistan"
    assert rec["source"] == "semanticscholar"


def test_normalize_s2_paper_captures_publication_date():
    raw = {"title": "T", "year": 2022, "publicationDate": "2022-03-15"}
    assert normalize_s2_paper(raw)["publication_date"] == "2022-03-15"


def test_normalize_s2_paper_missing_publication_date_is_none():
    raw = {"title": "T", "year": 2022}
    assert normalize_s2_paper(raw)["publication_date"] is None


def test_normalize_crossref_item_shapes_record():
    raw = {
        "title": ["T2"],
        "DOI": "10.3/y",
        "container-title": ["J"],
        "issued": {"date-parts": [[2019]]},
        "is-referenced-by-count": 5,
        "subject": ["Economics"],
        "type": "journal-article",
        "author": [
            {
                "given": "C",
                "family": "D",
                "affiliation": [{"name": "X University, Turkey"}],
            }
        ],
    }
    rec = normalize_crossref_item(raw)
    assert rec["doi"] == "10.3/y" and rec["publication_year"] == 2019
    assert rec["topic_names"] == ["Economics"]
    assert rec["authors"][0]["full_name"] == "C D"
    assert rec["source"] == "crossref"
    assert rec["publication_date"] is None


def test_normalize_crossref_item_builds_full_date_when_month_day_present():
    raw = {
        "title": ["T2"],
        "DOI": "10.3/y",
        "container-title": ["J"],
        "issued": {"date-parts": [[2019, 6, 4]]},
        "is-referenced-by-count": 5,
        "subject": ["Economics"],
        "type": "journal-article",
        "author": [],
    }
    rec = normalize_crossref_item(raw)
    assert rec["publication_date"] == "2019-06-04"


def test_normalize_crossref_item_year_only_gives_no_date():
    raw = {
        "title": ["T2"],
        "DOI": "10.3/y",
        "container-title": ["J"],
        "issued": {"date-parts": [[2019]]},
        "is-referenced-by-count": 5,
        "subject": ["Economics"],
        "type": "journal-article",
        "author": [],
    }
    rec = normalize_crossref_item(raw)
    assert rec["publication_date"] is None
