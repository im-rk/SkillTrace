"""
Logging with a request-correlation id that follows work across process boundaries.

A submission's life spans three execution contexts -- the HTTP request, a Redis
Stream message, and a Celery task. One id, minted (or accepted) at the edge and
carried in the stream payload and the task kwargs, lets a single grep
reconstruct the whole lifecycle instead of cross-referencing timestamps.
"""
import contextvars
import logging
import re
import uuid
from contextlib import contextmanager
from typing import Iterator

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

NO_REQUEST_ID = "-"
# An inbound X-Request-ID is client-controlled and ends up in every log line, so
# only accept a boring shape (no whitespace/newlines -> no log injection).
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def new_request_id() -> str:
    return uuid.uuid4().hex


def sanitize_request_id(candidate: str | None) -> str:
    return candidate if candidate and _VALID_REQUEST_ID.match(candidate) else new_request_id()


def current_request_id() -> str | None:
    return request_id_var.get()


@contextmanager
def use_request_id(request_id: str | None) -> Iterator[None]:
    """Binds the id for the duration of the block (a queue consumer or Celery task
    restoring the id of the request that caused its work). No id -> leaves it unset."""
    token = request_id_var.set(request_id)
    try:
        yield
    finally:
        request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or NO_REQUEST_ID
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent. API and Celery worker both call this so their lines are formatted identically."""
    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(h, "_skilltrace", False) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler._skilltrace = True  # type: ignore[attr-defined]
    handler.addFilter(RequestIdFilter())  # on the handler, so third-party records get the id too
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
