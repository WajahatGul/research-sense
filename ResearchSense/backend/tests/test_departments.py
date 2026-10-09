"""Departments are a place to browse from, not a count with nowhere to go."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_every_department_is_listed_with_its_people_and_papers():
    rows = client.get("/api/departments").json()
    names = client.get("/api/researchers/departments").json()
    assert {d["name"] for d in rows} == set(names)
    cs = next(d for d in rows if d["name"] == "Computer Science")
    listed = client.get(
        "/api/researchers", params={"department": "Computer Science", "page_size": 1}
    ).json()["total"]
    assert cs["researchers"] == listed
    assert cs["publications"] > 0 and cs["top_areas"]


def test_largest_department_comes_first():
    rows = client.get("/api/departments").json()
    sizes = [d["researchers"] for d in rows]
    assert sizes == sorted(sizes, reverse=True)
