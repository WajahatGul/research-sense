"""Publication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_publication_service
from app.schemas.common import Paginated
from app.schemas.publication import Publication
from app.services.publication_service import PublicationService

router = APIRouter(prefix="/api/publications", tags=["publications"])


@router.get("", response_model=Paginated[Publication])
def list_publications(
    q: str | None = None,
    year: int | None = None,
    topic_id: int | None = None,
    author_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    service: PublicationService = Depends(get_publication_service),
):
    return service.list(
        query=q, year=year, topic_id=topic_id, author_id=author_id,
        page=page, page_size=page_size,
    )


@router.get("/years", response_model=list[int])
def list_years(service: PublicationService = Depends(get_publication_service)):
    return service.years()


@router.get("/{publication_id}", response_model=Publication)
def get_publication(
    publication_id: int,
    service: PublicationService = Depends(get_publication_service),
):
    pub = service.get(publication_id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return pub
