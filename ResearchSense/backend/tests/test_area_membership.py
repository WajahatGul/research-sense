"""One answer to 'who works on this area?', wherever it is asked."""

from fastapi.testclient import TestClient

from app.core.areas import works_in
from app.main import app

client = TestClient(app)
ML = 368  # Machine Learning


def test_listed_expertise_counts_as_working_in_an_area():
    person = {"research_areas": ["Radiomics and Machine Learning in Medical Imaging"],
              "expertise_areas": ["Machine Learning"]}
    assert works_in(person, "machine  learning")
    assert not works_in(person, "Cybersecurity")


def test_the_area_page_lists_its_best_known_people_first():
    people = client.get("/api/researchers", params={"topic_id": ML, "page_size": 5}).json()
    assert people["items"][0]["full_name"] == "Shehzad Khalid"


def test_head_count_list_and_assistant_agree():
    count = client.get(f"/api/topics/{ML}").json()["researcher_count"]
    listed = client.get("/api/researchers", params={"topic_id": ML, "page_size": 1}).json()["total"]
    answer = client.post("/api/chat", json={"message": "Who works on machine learning?",
                                           "history": []}).json()["answer"]
    assert count == listed
    assert answer.startswith(f"{count} researchers work on Machine Learning")


def test_an_unknown_area_lists_no_one():
    assert client.get("/api/researchers", params={"topic_id": 999999}).json()["total"] == 0


def test_an_area_includes_papers_on_its_narrower_topics():
    area = client.get(f"/api/topics/{ML}").json()
    listed = client.get("/api/publications", params={"topic_id": ML, "page_size": 1}).json()["total"]
    assert area["publication_count"] == listed > 100  # was 4: exact label only


def test_every_label_on_a_paper_counts_not_only_the_first_four():
    rows = client.get("/api/topics", params={"q": "Islamic Finance and Banking Studies"}).json()
    area = next(t for t in rows if t["topic_name"] == "Islamic Finance and Banking Studies")
    assert area["publication_count"] >= 231  # showed 59


def test_single_words_are_not_matched_inside_longer_names():
    from app.core.areas import paper_areas
    topics = [{"topic_id": 1, "topic_name": "Health"},
              {"topic_id": 2, "topic_name": "Machine Learning"}]
    pubs = [{"publication_id": 9, "topics": [],
             "topic_names": ["Health Informatics and Machine Learning Applications"]}]
    assert paper_areas(topics, pubs)[0][9] == {2}


def test_areas_without_papers_sink_in_suggestions():
    from app.services.typeahead_service import suggest

    top = suggest("machine learning", None, 8)
    areas = [s for s in top if s.kind == "topic"]
    assert areas[0].label == "Machine Learning"
    assert "182" in areas[0].detail or "publications" in areas[0].detail
    assert "Machine Learning Data Mining Big Data" not in [s.label for s in top[:4]]
