"""Request id propagation and access logging (pure ASGI, no BaseHTTPMiddleware)."""

import logging
import re
import time
import uuid
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import REQUEST_ID_HEADER
from app.core.logging import request_id_ctx

logger = logging.getLogger("app.access")

# Client-supplied ids are accepted only in a safe, bounded format (log-injection guard).
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_QUIET_PATHS = {"/health"}


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                if REQUEST_ID_HEADER not in headers:
                    headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            path = scope.get("path", "")
            extra: dict[str, Any] = {
                "method": scope.get("method"),
                "path": path,  # path only: query strings may carry tokens
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            level = logging.DEBUG if path in _QUIET_PATHS else logging.INFO
            logger.log(level, "request", extra=extra)
            request_id_ctx.reset(token)
