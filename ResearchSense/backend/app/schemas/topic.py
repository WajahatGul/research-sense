"""Research topic / area schemas."""

from __future__ import annotations

from pydantic import BaseModel


class Topic(BaseModel):
    """A research area used to classify publications and researchers."""

    topic_id: int
    topic_name: str
    description: str = ""
    icon: str = "sparkles"
    publication_count: int = 0
    researcher_count: int = 0
    source: str = "sample"
    # The broad field it belongs to (OpenAlex's hierarchy; see
    # scripts/classify_topics.py). "" when it could not be placed.
    field: str = ""
    domain: str = ""
    field_source: str = ""  # "openalex" or "department" (a best guess)


class TopicRef(BaseModel):
    """Lightweight topic reference embedded in other resources."""

    topic_id: int
    topic_name: str
