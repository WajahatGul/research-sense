from app.services.analytics_service import AnalyticsService


def test_department_totals_counts_both_sides():
    researchers = [
        {"researcher_id": 1, "campus": "K", "department": "Psychology"},
        {"researcher_id": 2, "campus": "K", "department": "Psychology"},
        {"researcher_id": 3, "campus": "K", "department": "Law"},
    ]
    pubs = [{"campus": "K", "citation_count": 4, "publication_year": 2020,
             "authors": [{"researcher_id": 1}]}]
    rows = AnalyticsService._department_totals(researchers, pubs)
    psych = next(r for r in rows if r["department"] == "Psychology")
    assert psych["researchers"] == 2
    assert psych["publications"] == 1 and psych["citations"] == 4
    law = next(r for r in rows if r["department"] == "Law")
    assert law["publications"] == 0


def test_international_split_by_year():
    pubs = [{"publication_year": 2020, "international": True},
            {"publication_year": 2020, "international": False},
            {"publication_year": 2021, "international": False}]
    rows = AnalyticsService._international_split(pubs)
    assert rows == [{"year": 2020, "international": 1, "domestic": 1},
                    {"year": 2021, "international": 0, "domestic": 1}]
