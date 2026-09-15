"""
Bridges a sync Celery task body to this codebase's async-first application
code. Each call gets its own event loop -- Celery tasks run in separate
worker processes/threads, so there's no shared loop to reuse.
"""
import asyncio
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    return asyncio.run(coro)
