"""Topic endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_topic_service
from app.schemas.topic import Topic
from app.services.topic_service import TopicService

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=list[Topic])
def list_topics(
    q: str | None = None,
    service: TopicService = Depends(get_topic_service),
):
    return service.list(query=q)


@router.get("/{topic_id}", response_model=Topic)
def get_topic(
    topic_id: int,
    service: TopicService = Depends(get_topic_service),
):
    topic = service.get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic
