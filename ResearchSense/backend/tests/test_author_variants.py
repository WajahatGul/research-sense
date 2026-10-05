"""One person, one profile — but only when the record proves it.

Searching "arif" used to show Arif Ur Rahman and, beside him, a stub called
"Arif ur" holding one of his papers: OpenAlex had split him across two IDs.
"""

from app.repositories.mock.publications import MockPublicationRepository
from app.repositories.mock.researchers import MockResearcherRepository
from scripts.merge_author_variants import apply_merges, find_merges, name_fits


def _person(rid, name, source="scraped"):
    return {
        "researcher_id": rid,
        "full_name": name,
        "source": source,
        "publication_count": 1,
        "citation_count": 0,
    }


def _paper(pid, authors, topics=("Digital Preservation",), title="A paper"):
    return {
        "publication_id": pid,
        "title": title,
        "topic_names": list(topics),
        "authors": [{"researcher_id": rid, "full_name": n} for rid, n in authors],
    }


FACULTY = _person(1, "Arif Ur Rahman")
STUB = _person(2, "Arif ur", source="openalex")
COAUTHOR = _person(3, "Muhammad Muzammal")


def test_name_fits_shortened_and_transliterated_forms():
    assert name_fits("Arif ur", "Arif Ur Rahman")
    assert name_fits("Arif Ur Rehman", "Arif Ur Rahman")
    assert name_fits("M. Fahad Mahmood", "Muhammad Fahad Mahmood")
    assert not name_fits("Arif", "Arif Ur Rahman")  # one word proves nothing
    assert not name_fits("Arif Khattak", "Arif Ur Rahman")


def test_stub_with_shared_coauthor_and_subject_is_merged():
    people = [FACULTY, STUB, COAUTHOR]
    papers = [
        _paper(10, [(1, "Arif Ur Rahman"), (3, "Muhammad Muzammal")]),
        _paper(11, [(2, "Arif Ur"), (3, "Muhammad Muzammal")]),
    ]
    merges = find_merges(people, papers)
    assert [(m["stub_id"], m["into_id"]) for m in merges] == [(2, 1)]

    kept, papers = apply_merges([dict(p) for p in people], papers, merges)
    assert 2 not in {p["researcher_id"] for p in kept}
    assert papers[1]["authors"][0]["researcher_id"] == 1
    arif = next(p for p in kept if p["researcher_id"] == 1)
    assert arif["publication_count"] == 2
    assert arif["also_published_as"][0]["name"] == "Arif ur"


def test_similar_name_alone_is_not_enough():
    people = [FACULTY, STUB, COAUTHOR]
    papers = [
        _paper(10, [(1, "Arif Ur Rahman"), (3, "Muhammad Muzammal")]),
        _paper(11, [(2, "Arif Ur")]),  # no shared co-author
    ]
    assert find_merges(people, papers) == []


def test_shared_coauthor_on_a_different_subject_is_not_enough():
    people = [FACULTY, STUB, COAUTHOR]
    papers = [
        _paper(
            10,
            [(1, "Arif Ur Rahman"), (3, "Muhammad Muzammal")],
            topics=("Digital Preservation",),
            title="News archives",
        ),
        _paper(
            11,
            [(2, "Arif Ur"), (3, "Muhammad Muzammal")],
            topics=("Battery Technology",),
            title="Electric vehicles",
        ),
    ]
    assert find_merges(people, papers) == []


def test_two_names_on_one_paper_are_two_people():
    people = [FACULTY, STUB, COAUTHOR]
    papers = [
        _paper(10, [(1, "Arif Ur Rahman"), (3, "Muhammad Muzammal")]),
        _paper(11, [(2, "Arif Ur"), (1, "Arif Ur Rahman"), (3, "Muhammad Muzammal")]),
    ]
    assert find_merges(people, papers) == []


def test_searching_arif_shows_arif_ur_rahman_once():
    names = [r.full_name for r in MockResearcherRepository().list(query="arif")]
    assert "Arif Ur Rahman" in names
    assert "Arif ur" not in names


def test_the_split_off_paper_is_on_his_profile():
    pub = MockPublicationRepository().get(5371)
    assert pub is not None
    assert [a.researcher_id for a in pub.authors][0] == 8


def test_the_old_spelling_still_finds_him():
    names = [r.full_name for r in MockResearcherRepository().list(query="Arif ur")]
    assert names[0] == "Arif Ur Rahman"


def test_corpus_has_nothing_left_to_merge():
    """The data ships already merged; re-running the script is a no-op."""
    from app.repositories.loader import load

    assert find_merges(load("researchers"), load("publications")) == []
