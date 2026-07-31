from scripts.fetch_publications import (
    backfill_topic_names,
    derive_research_areas,
    expertise_field_guard,
    international_of,
    merge_supplementary,
)


def test_field_guard_matches_on_token_overlap():
    assert expertise_field_guard(["Machine Learning"], "machine learning, vision")


def test_field_guard_includes_department_text():
    assert expertise_field_guard(["Clinical Psychology"], "psychology")


def test_field_guard_rejects_disjoint_fields():
    assert not expertise_field_guard(["Organic Chemistry"], "machine learning")


def test_field_guard_empty_expertise_rejects():
    assert not expertise_field_guard(["Anything"], "")


def test_international_true_for_non_pk():
    assert international_of([{"name": "MIT", "country": "US"}])


def test_international_false_for_pk_only_or_unknown():
    assert not international_of(
        [{"name": "Bahria", "country": "PK"}, {"name": "X", "country": None}]
    )
    assert not international_of([])


def test_derive_areas_from_publication_topics():
    r = {"expertise_areas": ["Old Area"]}
    pubs = [
        {"topic_names": ["Neuroscience", "Psychiatry"]},
        {"topic_names": ["Neuroscience"]},
    ]
    areas = derive_research_areas(r, pubs)
    assert areas[0] == "Neuroscience" and "Psychiatry" in areas


def test_derive_areas_falls_back_to_expertise():
    r = {"expertise_areas": ["Corporate Law", "Taxation"]}
    assert derive_research_areas(r, []) == ["Corporate Law", "Taxation"]


def test_merge_supplementary_dedupes_by_doi_then_title():
    primary = [{"doi": "10.1/a", "title": "T1", "publication_year": 2020}]
    extra = [
        {"doi": "10.1/A", "title": "Other", "publication_year": 2020},
        {"doi": None, "title": "T1!", "publication_year": 2020},
        {"doi": None, "title": "Brand New", "publication_year": 2021},
    ]
    merged = merge_supplementary(primary, extra)
    titles = [p["title"] for p in merged]
    assert titles == ["T1", "Brand New"]


def test_backfill_fills_missing_topic_names_from_topics():
    pubs = [
        {
            "topics": [
                {"topic_id": 1, "topic_name": "AI"},
                {"topic_id": 2, "topic_name": "Robotics"},
            ]
        }
    ]
    backfill_topic_names(pubs)
    assert pubs[0]["topic_names"] == ["AI", "Robotics"]


def test_backfill_fills_empty_topic_names_list_from_topics():
    pubs = [{"topic_names": [], "topics": [{"topic_id": 1, "topic_name": "AI"}]}]
    backfill_topic_names(pubs)
    assert pubs[0]["topic_names"] == ["AI"]


def test_backfill_leaves_existing_topic_names_untouched():
    pubs = [
        {
            "topic_names": ["Machine Learning"],
            "topics": [{"topic_id": 1, "topic_name": "AI"}],
        }
    ]
    backfill_topic_names(pubs)
    assert pubs[0]["topic_names"] == ["Machine Learning"]


def test_backfill_leaves_publication_with_neither_field_empty():
    pubs = [{}]
    backfill_topic_names(pubs)
    assert not pubs[0].get("topic_names")
