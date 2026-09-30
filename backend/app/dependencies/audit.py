"""Dependency that captures request metadata for audit rows."""

from fastapi import Request

from app.core.request_context import request_id_from_scope
from app.services.audit import AuditContext


def get_audit_context(request: Request) -> AuditContext:
    """Build the audit context (client IP + user agent) for this request.

    The IP is the direct peer address. ``X-Forwarded-For`` is deliberately not
    trusted here: without a configured trusted proxy any client could forge
    it. Behind a reverse proxy, run uvicorn with ``--proxy-headers`` so the
    peer address is rewritten by the server itself.
    """
    return AuditContext(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=request_id_from_scope(request.scope),
    )
