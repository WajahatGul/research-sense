"""The assistant must answer from the workspace it is serving.

A signed-up institution's chatbot reads that institution's records — never the
bundled demo corpus — and keeps working before its semantic index exists,
because the structured fast paths read the saved JSON directly.
"""

from __future__ import annotations

import pytest

from app.core import tenancy
from app.repositories import loader, workspaces
from app.schemas.chat import ChatTurn
from app.schemas.researcher import Researcher
from app.services import chat_service as chat_module
from app.services.chat_service import INDEX_MISSING_MESSAGE, ChatService
from app.services.rag import authored, workspace_index

WS = "chat-institution"

OWNER = {
    "researcher_id": 1,
    "full_name": "Sara Ahmed",
    "designation": "Associate Professor",
    "academic_rank": "Associate Professor",
    "department": "Computer Science",
    "campus": "Main campus",
    "email": "sara@example.edu",
    "publication_count": 1,
    "citation_count": 4,
    "research_areas": ["Federated Learning"],
    "topics": [{"topic_id": 1, "topic_name": "Federated Learning"}],
}

PAPER = {
    "publication_id": 1,
    "title": "Federated Learning on Edge Devices",
    "publication_year": 2023,
    "journal_name": "IEEE Access",
    "citation_count": 4,
    "authors": [{"researcher_id": 1, "full_name": "Sara Ahmed", "order": 1}],
}


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """A throwaway workspace with data but no semantic index."""
    monkeypatch.setattr(loader, "WORKSPACES_DIR", tmp_path / "workspaces")
    # Follow-up normalization would otherwise reach for the language model.
    monkeypatch.setattr(chat_module, "normalize_query", lambda q, _h: q)
    loader.clear_cache()
    loader.save("researchers", [OWNER], WS)
    loader.save("publications", [PAPER], WS)
    loader.save("topics", [{"topic_id": 1, "topic_name": "Federated Learning"}], WS)
    loader.set_workspace(WS)
    yield WS
    loader.set_workspace(None)
    loader.clear_cache()
    authored._Store.reset()
    tenancy.forget()


def test_fast_paths_read_the_active_workspace():
    """The demo corpus has hundreds of researchers; this workspace has one."""
    assert [r["full_name"] for r in authored._Store.researchers()] == ["Sara Ahmed"]
    assert len(authored._Store.pubs()) == 1

    loader.set_workspace(None)
    assert len(authored._Store.researchers()) > 1


def test_department_question_is_answered_without_an_index():
    answer = ChatService().answer("who are the researchers in computer science?").answer
    assert "Sara Ahmed" in answer
    assert answer != INDEX_MISSING_MESSAGE


def test_authored_question_is_answered_without_an_index():
    answer = ChatService().answer("what papers has Sara Ahmed written?").answer
    assert "Federated Learning on Edge Devices" in answer


def test_open_ended_question_explains_what_it_can_answer():
    """No index yet: say what still works rather than a build command."""
    reply = ChatService().answer(
        "summarise the methodology used in the edge computing work",
        [ChatTurn(role="user", content="hello")],
    )
    assert reply.answer == INDEX_MISSING_MESSAGE
    assert "python -m" not in reply.answer


def test_profiles_are_branded_with_the_workspaces_own_institution(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(workspaces, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(workspaces.WorkspaceStore, "_instance", None)
    account = workspaces.WorkspaceStore.instance().create(
        email="owner@meridian.edu",
        password_hash="x",
        institution_name="Meridian University",
        full_name="Sara Ahmed",
        department="Computer Science",
        campus="Main campus",
        orcid_id=None,
    )
    loader.set_workspace(account["workspace_id"])
    assert tenancy.institution_name() == "Meridian University"

    profile = Researcher(
        researcher_id=1,
        full_name="Sara Ahmed",
        designation="Professor",
        department="Computer Science",
        institution="Bahria University",
    )
    assert profile.institution == "Meridian University"


def test_index_chunks_cover_the_workspaces_own_records():
    chunks = workspace_index.chunks_for(WS)
    kinds = {c["kind"] for c in chunks}
    assert kinds == {"researcher", "publication", "topic"}
    assert any("Sara Ahmed" in c["text"] for c in chunks)
    assert any("Federated Learning on Edge Devices" in c["text"] for c in chunks)


def test_the_demo_index_is_never_rebuilt_from_a_workspace_write():
    """It carries paper full text a structured rebuild would destroy."""
    with pytest.raises(ValueError, match="build_index"):
        workspace_index.rebuild(loader.DEFAULT_WORKSPACE)
