"""Fixed-window rate limiting for sensitive endpoints (pure ASGI, in-process).

Scope and honest limits: counters live in this process only, so with N workers the effective
limit is N times higher, and the key is the TCP peer address (behind a proxy that is the proxy,
unless the deployment passes real client addresses, e.g. uvicorn `--proxy-headers` with a trusted
proxy). A shared store (Redis) is the production upgrade and is deliberately not added here.
The Razorpay webhook is excluded: it is signature-authenticated and the sender retries.
"""

import time

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

# (method, path-prefix-or-exact, group). First match wins.
_RULES: tuple[tuple[str, str, str], ...] = (
    ("POST", "/payments/create-order", "payments"),
    ("POST", "/payments/verify", "payments"),
    ("POST", "/bookings/quote", "booking-quote"),
    ("POST", "/bookings/", "booking-write"),  # cancel
    ("POST", "/bookings", "booking-write"),
    ("POST", "/auth/profile", "auth"),
    ("POST", "/owners/venues/", "upload"),  # image upload lives under here
    ("GET", "/admin/exports/", "export"),
    ("GET", "/places/", "places"),
)
_MAX_KEYS = 10_000


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, *, prefix: str, per_minute: int) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")
        self.per_minute = per_minute
        self._windows: dict[tuple[str, str], tuple[int, int]] = {}  # key -> (window_id, count)

    def _group(self, method: str, path: str) -> str | None:
        if not path.startswith(self.prefix):
            return None
        rel = path[len(self.prefix) :]
        for m, p, group in _RULES:
            if m != method:
                continue
            if group == "upload":
                if rel.startswith(p) and rel.endswith("/images"):
                    return group
                continue
            if rel == p or (p.endswith("/") and rel.startswith(p)):
                return group
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.per_minute <= 0:
            await self.app(scope, receive, send)
            return
        group = self._group(scope["method"], scope.get("path", ""))
        if group is None:
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        window = int(now // 60)
        client = scope.get("client")
        key = (client[0] if client else "unknown", group)
        win, count = self._windows.get(key, (window, 0))
        if win != window:
            win, count = window, 0
        count += 1
        if len(self._windows) >= _MAX_KEYS:
            self._windows = {k: v for k, v in self._windows.items() if v[0] == window}
        self._windows[key] = (win, count)

        if count > self.per_minute:
            retry = max(1, int(60 - (now % 60)))
            response = error_response(
                Request(scope),
                status_code=429,
                code="RATE_LIMITED",
                message="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(retry)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
