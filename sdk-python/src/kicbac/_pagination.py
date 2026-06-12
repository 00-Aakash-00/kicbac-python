"""Lazy auto-pagination over query.php ``page_number`` pages."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TypeVar

T = TypeVar("T")


def paginate(fetch: Callable[[int], list[T]], page_size: int) -> Iterator[T]:
    """Yield items page by page; fetch page N+1 only after page N is exhausted
    and only if page N was full (``len(batch) == page_size``)."""
    page_number = 0
    while True:
        batch = fetch(page_number)
        yield from batch
        if len(batch) < page_size:
            return
        page_number += 1


async def paginate_async(
    fetch: Callable[[int], Awaitable[list[T]]], page_size: int
) -> AsyncIterator[T]:
    """Async twin of :func:`paginate`."""
    page_number = 0
    while True:
        batch = await fetch(page_number)
        for item in batch:
            yield item
        if len(batch) < page_size:
            return
        page_number += 1
