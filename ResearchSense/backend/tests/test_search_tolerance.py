"""Search must forgive the ways people actually type.

Each case here returned zero (or a different set) under the old literal
substring match, which told visitors "we have nothing" for data we hold.
"""

from app.core.textsearch import Query, correct, tokens
from app.repositories.mock.publications import MockPublicationRepository
from app.repositories.mock.researchers import MockResearcherRepository
from app.repositories.mock.topics import MockTopicRepository
from app.services.publication_service import PublicationService
from app.services.researcher_service import ResearcherService


def _people(q: str) -> list[str]:
    return [r.full_name for r in MockResearcherRepository().list(query=q)]


def test_tokens_are_lowercased_and_singular():
    assert tokens("Smart Cities, IoT Networks") == ["smart", "city", "iot", "network"]


def test_query_matches_words_in_any_order():
    assert Query("naseer kashif").matches("Muhammad Kashif Naseer")


def test_query_bridges_a_missing_space():
    assert Query("cybersecurity").matches("Cyber Security")
    assert Query("cyber security").matches("Cybersecurity")


def test_name_order_does_not_matter():
    assert set(_people("naseer kashif")) == set(_people("kashif naseer"))
    assert "Muhammad Kashif Naseer" in _people("naseer kashif")


def test_exact_name_is_ranked_first():
    assert _people("Muhammad Kashif Naseer")[0] == "Muhammad Kashif Naseer"


def test_plural_and_singular_find_the_same_papers():
    repo = MockPublicationRepository()
    city = {p.publication_id for p in repo.list(query="smart city")}
    cities = {p.publication_id for p in repo.list(query="smart cities")}
    assert city and city == cities


def test_research_area_names_are_searchable():
    # A person tagged with an area should be findable by that area even when
    # the words never appear in their free-text expertise.
    repo = MockResearcherRepository()
    person = next(r for r in repo.list() if r.topics)
    area = person.topics[0].topic_name
    assert person.full_name in _people(area)


def test_typo_is_corrected_and_reported():
    service = ResearcherService(MockResearcherRepository())
    page = service.list(query="machin lerning")
    assert page.total > 0
    assert page.corrected_query == "machine learning"


def test_no_correction_is_claimed_when_the_query_already_matched():
    service = ResearcherService(MockResearcherRepository())
    assert service.list(query="machine learning").corrected_query is None


def test_publication_typo_is_corrected():
    service = PublicationService(MockPublicationRepository())
    page = service.list(query="smrt citys")
    assert page.total > 0
    assert page.corrected_query == "smart city"


def test_unfixable_gibberish_still_returns_nothing():
    service = ResearcherService(MockResearcherRepository())
    page = service.list(query="zzqxv")
    assert page.total == 0 and page.corrected_query is None


def test_correct_returns_none_when_nothing_changes():
    assert correct("machine learning", {"machine": 3, "learning": 3}) is None


def test_correct_prefers_the_common_word_over_a_rare_typo_in_the_data():
    vocab = {"learning": 500, "leraning": 1}
    assert correct("lerning", vocab) == "learning"


def test_area_search_ranks_the_closest_name_first():
    names = [t.topic_name for t in MockTopicRepository().list(query="machine learning")]
    assert names and "machine learning" in names[0].lower()
