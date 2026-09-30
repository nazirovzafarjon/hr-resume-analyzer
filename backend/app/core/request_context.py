"""Request-id propagation.

Every request gets an id (the client's ``X-Request-ID`` when it is a sane
token, otherwise a fresh UUID). It is stored in ``request.state.request_id``,
echoed in the ``X-Request-ID`` response header and saved with any recorded
system error, so an administrator can match a row on the System Errors page
with the server log line and with what the user saw.

It is also where unhandled exceptions are *recorded*: the middleware sits
inside Starlette's ServerErrorMiddleware, sees every exception on its way out
and passes it to ``on_unhandled_error`` before re-raising, so the error is
stored whether the app runs in DEBUG mode (traceback page) or not (JSON 500).

Implemented as plain ASGI middleware (not ``BaseHTTPMiddleware``) so it adds
no buffering and never interferes with streaming/file responses or
background tasks.
"""

import logging
import re
import uuid
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{8,64}$")


def request_id_from_scope(scope: Scope) -> str | None:
    """The id assigned to this request, if the middleware ran."""
    state = scope.get("state") or {}
    return state.get("request_id")


class RequestContextMiddleware:
    """Assign a request id, expose it on the response, report crashes."""

    def __init__(
        self,
        app: ASGIApp,
        on_unhandled_error: Callable[[Scope, Exception], None] | None = None,
    ) -> None:
        self.app = app
        self.on_unhandled_error = on_unhandled_error

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = ""
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        # Untrusted input: only accept a short token of safe characters so the
        # value can never inject into logs or headers.
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"x-request-id" for name, _ in headers):
                    headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            if self.on_unhandled_error is not None:
                try:
                    # The callback does blocking I/O (a DB insert).
                    await run_in_threadpool(self.on_unhandled_error, scope, exc)
                except Exception:  # noqa: BLE001 -- never mask the original error
                    logger.exception("Error reporter failed")
            raise
