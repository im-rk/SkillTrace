"""
Bridges a sync Celery task body to this codebase's async-first application code.

One event loop per worker *process*, run in a background thread and reused by
every call. A fresh `asyncio.run()` per call hands the module-level engine's
pooled asyncpg connections (bound to the loop that created them) to a later,
different loop. The loop is keyed on the OS pid because Celery's prefork pool
forks children, and fork() carries only the calling thread: a loop thread
started before the fork does not exist in the child (see docs/adr/0008).
"""
import asyncio
import os
import threading
from typing import Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_pid
    with _loop_lock:
        if _loop is None or _loop_pid != os.getpid():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True, name="async-task-loop").start()
            _loop, _loop_pid = loop, os.getpid()
        return _loop


def run_async(coro: Coroutine[None, None, T]) -> T:
    return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result()
