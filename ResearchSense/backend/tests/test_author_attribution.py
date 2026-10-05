"""A paper is credited to a profile only when the printed name is theirs."""

from app.repositories import loader
from app.repositories.mock.researchers import MockResearcherRepository
from scripts.author_identity import printed_name_fits
from scripts.unlink_misattributed import find_unlinks


def test_different_people_sharing_common_words_do_not_fit():
    assert not printed_name_fits("Syed Toqeer Haider", "Syed Haider Ali Shah")
    assert not printed_name_fits("Mohsin Raza Khan", "Mohsin Hassan Khan")
    assert not printed_name_fits("Muhammad Zunnurain Hussain", "Muhammad Hussain")
    assert not printed_name_fits("Muhammad Aasim Qureshi", "Muhammad Asif Qureshi")
    assert not printed_name_fits(
        "Muhammad Rahman", "Syed Muhammad Khaliq-ur-Rahman Raazi"
    )


def test_the_same_person_written_differently_fits():
    assert printed_name_fits("Dr. Maqbool Hassan", "Maqbool Hassan")
    assert printed_name_fits("Jawad Abdullah Butt", "Jawwad Abdullah Butt")
    assert printed_name_fits("Saif Ullah Shaikh", "Saifullah Shaikh")
    assert printed_name_fits("Fazl-e-Hadi", "Fazle Hadi")
    assert printed_name_fits("Safdar Rizvi", "Syed Safdar Ali Rizvi")
    assert printed_name_fits("Muhammad Fahad Mahmood", "M. Fahad Mahmood")
    assert printed_name_fits("Kashif Naseer Qureshi", "Muhammad Kashif Naseer")
    assert printed_name_fits("A. Jamil", "Asma Jamil")
    assert printed_name_fits("Imran Farid Nizami", "Imran Fareed Nizami")


def test_the_corpus_has_no_misattributed_links_left():
    assert find_unlinks(loader.load("researchers"), loader.load("publications")) == []


def test_power_systems_papers_are_no_longer_on_the_hr_professor():
    repo = MockResearcherRepository()
    shah = next(
        r
        for r in repo.list(query="Syed Haider Ali Shah")
        if r.full_name == "Syed Haider Ali Shah"
    )
    printed = {
        a["full_name"]
        for p in loader.load("publications")
        for a in p["authors"]
        if a.get("researcher_id") == shah.researcher_id
    }
    assert "Syed Toqeer Haider" not in printed
    assert "Syed Waseem Haider" not in printed


def test_profile_counts_match_the_papers_they_list():
    pubs = loader.load("publications")
    listed: dict[int, int] = {}
    for p in pubs:
        for rid in {a.get("researcher_id") for a in p["authors"]} - {None}:
            listed[rid] = listed.get(rid, 0) + 1
    for r in loader.load("researchers"):
        if not loader.is_extended(r):
            assert r["publication_count"] == listed.get(r["researcher_id"], 0), r[
                "full_name"
            ]
