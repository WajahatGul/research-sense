from scripts.fetch_sources import (country_from_affiliation, dedupe_key,
                                   normalize_s2_paper, normalize_crossref_item)


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
    raw = {"title": "T", "year": 2022, "externalIds": {"DOI": "10.2/x"},
           "venue": "VenueX", "citationCount": 3, "fieldsOfStudy": ["Biology"],
           "authors": [{"name": "A B", "affiliations": ["Uni, Pakistan"]}],
           "publicationTypes": ["JournalArticle"]}
    rec = normalize_s2_paper(raw)
    assert rec["doi"] == "10.2/x" and rec["publication_year"] == 2022
    assert rec["topic_names"] == ["Biology"]
    assert rec["authors"][0]["affiliation"] == "Uni, Pakistan"
    assert rec["source"] == "semanticscholar"


def test_normalize_crossref_item_shapes_record():
    raw = {"title": ["T2"], "DOI": "10.3/y", "container-title": ["J"],
           "issued": {"date-parts": [[2019]]}, "is-referenced-by-count": 5,
           "subject": ["Economics"], "type": "journal-article",
           "author": [{"given": "C", "family": "D",
                       "affiliation": [{"name": "X University, Turkey"}]}]}
    rec = normalize_crossref_item(raw)
    assert rec["doi"] == "10.3/y" and rec["publication_year"] == 2019
    assert rec["topic_names"] == ["Economics"]
    assert rec["authors"][0]["full_name"] == "C D"
    assert rec["source"] == "crossref"
