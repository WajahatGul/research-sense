"""Generic in-memory pagination helper."""
from __future__ import annotations

from typing import Sequence, TypeVar

from app.schemas.common import Paginated

T = TypeVar("T")


def paginate(items: Sequence[T], page: int, page_size: int) -> Paginated[T]:
    """Slice a fully-materialised list into a paginated envelope."""
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    start = (page - 1) * page_size
    window = items[start:start + page_size]
    return Paginated[T](
        items=list(window),
        total=len(items),
        page=page,
        page_size=page_size,
    )
