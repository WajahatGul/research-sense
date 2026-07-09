"""Dependency wiring — binds concrete repositories to services.

This is the composition root. To move from mock JSON to a database, swap the
repository classes imported here; nothing else in the app changes.
"""
from __future__ import annotations

from functools import lru_cache

from app.repositories.mock.projects import MockProjectRepository
from app.repositories.mock.publications import MockPublicationRepository
from app.repositories.mock.researchers import MockResearcherRepository
from app.repositories.mock.stats import MockStatsRepository
from app.repositories.mock.topics import MockTopicRepository
from app.services.chat_service import ChatService
from app.services.project_service import ProjectService
from app.services.publication_service import PublicationService
from app.services.researcher_service import ResearcherService
from app.services.stats_service import StatsService
from app.services.topic_service import TopicService


@lru_cache
def get_researcher_service() -> ResearcherService:
    return ResearcherService(MockResearcherRepository())


@lru_cache
def get_publication_service() -> PublicationService:
    return PublicationService(MockPublicationRepository())


@lru_cache
def get_topic_service() -> TopicService:
    return TopicService(MockTopicRepository())


@lru_cache
def get_project_service() -> ProjectService:
    return ProjectService(MockProjectRepository())


@lru_cache
def get_stats_service() -> StatsService:
    return StatsService(MockStatsRepository())


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(MockResearcherRepository(), MockTopicRepository())
