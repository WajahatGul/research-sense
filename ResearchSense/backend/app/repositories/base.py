"""Abstract repository interfaces — the contract every data source implements.

Services depend on these ABCs, never on a concrete data source. A future
SQL/ORM layer implements the same methods and is injected in place of the mock.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.common import Stats
from app.schemas.project import Project
from app.schemas.publication import Publication
from app.schemas.researcher import Researcher, ResearcherDetail
from app.schemas.topic import Topic


class ResearcherRepository(ABC):
    @abstractmethod
    def list(
        self,
        *,
        query: str | None = None,
        department: str | None = None,
        designation: str | None = None,
        topic_id: int | None = None,
    ) -> list[Researcher]: ...

    @abstractmethod
    def get(self, researcher_id: int) -> ResearcherDetail | None: ...

    @abstractmethod
    def departments(self) -> list[str]: ...

    @abstractmethod
    def designations(self) -> list[str]: ...


class PublicationRepository(ABC):
    @abstractmethod
    def list(
        self,
        *,
        query: str | None = None,
        year: int | None = None,
        topic_id: int | None = None,
        author_id: int | None = None,
    ) -> list[Publication]: ...

    @abstractmethod
    def get(self, publication_id: int) -> Publication | None: ...


class TopicRepository(ABC):
    @abstractmethod
    def list(self, *, query: str | None = None) -> list[Topic]: ...

    @abstractmethod
    def get(self, topic_id: int) -> Topic | None: ...


class ProjectRepository(ABC):
    @abstractmethod
    def list(self, *, status: str | None = None) -> list[Project]: ...

    @abstractmethod
    def get(self, project_id: int) -> Project | None: ...


class StatsRepository(ABC):
    @abstractmethod
    def get_stats(self) -> Stats: ...
