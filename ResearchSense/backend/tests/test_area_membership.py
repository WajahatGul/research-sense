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
