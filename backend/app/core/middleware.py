"""
Pure-ASGI middleware (not BaseHTTPMiddleware: it would break streaming and
contextvar propagation) that gives every HTTP request a correlation id.
"""
import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var, sanitize_request_id

logger = logging.getLogger("skilltrace.access")
_QUIET_PATHS = {"/health"}


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = sanitize_request_id(incoming)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500  # what the client sees if the app dies before responding

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            if scope["path"] not in _QUIET_PATHS:
                logger.info(
                    "%s %s -> %s (%.0f ms)", scope["method"], scope["path"], status_code, (time.perf_counter() - started) * 1000
                )
            request_id_var.reset(token)
