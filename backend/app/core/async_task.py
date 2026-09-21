"""
Bridges a sync Celery task body to this codebase's async-first application
code.

Two failure modes were found the hard way via Phase 12's load test (the
first time this bridge ran repeatedly for real, across multiple tasks in a
live worker, instead of pytest calling the underlying coroutine directly):

1. A fresh `asyncio.run(coro)` per call means app.core.db.session.engine's
   pooled asyncpg connections -- bound to whichever loop created them -- can
   get handed to a *later* call's brand-new loop. Invalid, and on Windows it
   surfaced as `AttributeError: 'NoneType' object has no attribute 'send'`
   from a dead ProactorEventLoop transport.
2. The fix for #1 (one persistent loop, run forever in a background thread,
   reused by every call) breaks under Celery's *prefork* pool: fork() only
   carries the forking thread into the child process, not any other threads
   that were already running -- so a loop-driving thread started before
   fork() simply doesn't exist in the forked child, even though the child's
   copied module state still points at the loop object as if it does. Tasks
   silently corrupt (SQLAlchemy's greenlet bridge raised
   `MissingGreenlet: greenlet_spawn has not been called`) because nothing in
   that process was actually driving the loop.

Fix: key the cached loop+thread on the current OS pid, not just "has this
process ever called this before" -- a pid change (i.e. we're now running in
a fork() child) forces a genuinely fresh loop+thread in that process,
instead of reusing a reference to a thread that never existed there.
"""
import asyncio
import os
import sys
import threading
from typing import Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None
_loop_lock = threading.Lock()


def _new_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        # asyncpg + the default Windows ProactorEventLoop have a known
        # incompatibility (overlapped-I/O state can go bad under load) --
        # SelectorEventLoop doesn't use overlapped I/O and is the documented
        # workaround.
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_pid
    with _loop_lock:
        current_pid = os.getpid()
        if _loop is None or _loop_pid != current_pid:
            loop = _new_loop()
            threading.Thread(target=loop.run_forever, daemon=True, name="async-task-loop").start()
            _loop = loop
            _loop_pid = current_pid
        return _loop


def run_async(coro: Coroutine[None, None, T]) -> T:
    return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result()
