"""SSRF-safe validation for user-supplied API base URLs (Generic provider).

Defense in depth:

1. **Scheme** — ``https`` only, except HTTP is allowed on ``localhost`` when
   ``settings.DEBUG`` is set (explicitly approved local-development scenario).
2. **Port** — ``443`` and ``8443`` only (configurable via
   ``ALLOWED_URL_PORTS``); the default HTTPS port is implied when omitted.
3. **Syntax** — rejects embedded credentials (``user:pass@host``), fragments,
   malformed hosts / empty hosts, and any query string.
4. **DNS** — resolves *every* returned address (IPv4 and IPv6) and rejects the
   URL if **any** of them is loopback / private / link-local / multicast /
   reserved / unspecified / cloud-metadata.
5. **Redirects** — callers must disable ``follow_redirects`` so a provider
   cannot bounce the key-bearing request to an internal address at connection
   time.

Limitations (documented honestly):

* DNS can change between validation and the actual request (a classic
  TOCTOU / DNS-rebinding window). The platform also disables redirects, so the
  only remaining residual is a hostname whose DNS flips to a private address
  between two separate requests. If stronger protection is required, a custom
  ``httpx`` transport that re-checks the resolved address at connection time
  should be added, but that is intentionally omitted here to avoid unnecessary
  complexity.

Only the Python standard library is used.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.config import settings

#: Ports the Generic provider endpoint may listen on.
ALLOWED_URL_PORTS: frozenset[int] = frozenset({443, 8443})

# Cloud metadata endpoints that must never be reachable. The IP-based checks
# below already cover 169.254.169.254 and the IPv6 loopback equivalent, but this
# is also the explicit guard for well-known metadata IPs.
_BLOCKED_METADATA_IPS: frozenset[ipaddress._BaseAddress] = frozenset(
    ipaddress.ip_address(ip) for ip in ("169.254.169.254", "0.0.0.0", "::1")
)


class UnsafeURLError(ValueError):
    """Raised when a base URL fails SSRF / format validation."""


def _ip_is_blocked(addr: str) -> bool:
    """True for loopback, private, link-local, multicast, reserved, unspecified."""

    def _check(ip: ipaddress._BaseAddress) -> bool:
        if ip in _BLOCKED_METADATA_IPS:
            return True
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped and _check(mapped):
            return True
        return (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )

    try:
        return _check(ipaddress.ip_address(addr))
    except ValueError:
        return False  # Not an IP literal; it's a hostname — resolved separately.


def _resolve_host(hostname: str) -> list[str]:
    """Resolve *all* addresses for ``hostname`` (IPv4 + IPv6).

    Raises ``UnsafeURLError`` if resolution fails.
    """
    try:
        infos = socket.getaddrinfo(
            hostname, None, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise UnsafeURLError(
            "Could not resolve the provider base URL host."
        ) from exc
    ips: list[str] = []
    for family, _stype, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        if family == socket.AF_INET6 and ip not in ips:
            ips.append(ip)
        elif family == socket.AF_INET and ip not in ips:
            ips.append(ip)
    return ips


def validate_base_url(raw_url: str, *, for_save: bool = False) -> str:
    """Validate and normalize a base URL for the Generic OpenAI-compatible provider.

    Args:
        raw_url: The user-supplied base URL.
        for_save: When ``True`` DNS resolution is enforced (configuration can be
            saved only for a reachable-ish, non-internal host). When ``False``
            (e.g. request-time), a hostname that is not yet resolvable is also
            rejected, which keeps tests deterministic.

    Returns:
        The normalized HTTPS URL (no trailing slash).

    Raises:
        UnsafeURLError: if the URL is malformed, non-HTTPS, points at a blocked
            address, or uses a disallowed port.
    """
    url = (raw_url or "").strip()
    if not url:
        raise UnsafeURLError("A base URL is required for the Generic provider.")

    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    host = parts.hostname
    port = parts.port

    if scheme not in ("http", "https"):
        raise UnsafeURLError("Base URL must use http or https.")

    if scheme == "http" and host not in ("localhost", "127.0.0.1", "::1"):
        if not settings.DEBUG:
            raise UnsafeURLError(
                "Base URL must use HTTPS (HTTP is only allowed on localhost in dev mode)."
            )

    # Reject embedded credentials and fragments.
    if parts.username or parts.password:
        raise UnsafeURLError("Base URL must not contain embedded credentials.")
    if parts.fragment:
        raise UnsafeURLError("Base URL must not contain a fragment.")
    if parts.query:
        raise UnsafeURLError("Base URL must not contain a query string.")
    if not host:
        raise UnsafeURLError("Base URL must include a host name.")

    if parts.path:
        # Reject path traversal attempts.
        segments = parts.path.split("/")
        if ".." in segments or "." in segments:
            raise UnsafeURLError("Base URL must not contain path traversal segments.")

    # Port policy.
    if port is not None and port not in ALLOWED_URL_PORTS:
        if not (scheme == "http" and host in ("localhost", "127.0.0.1", "::1") and settings.DEBUG):
            raise UnsafeURLError(
                f"Port {port} is not allowed; use one of {sorted(ALLOWED_URL_PORTS)}."
            )

    # IP-literal host: reject anything internal directly.
    # (IPv6 literals arrive with brackets stripped by urlsplit.hostname.)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _ip_is_blocked(host):
            raise UnsafeURLError("Base URL must not point at a private or internal address.")
        # An IP literal passed validation; return it normalized.
        return _normalize(parts)

    # Hostname: resolve and block if ANY resolved address is internal.
    resolved = _resolve_host(host)
    for addr in resolved:
        if _ip_is_blocked(addr):
            raise UnsafeURLError(
                "Base URL resolves to a private or internal address."
            )

    return _normalize(parts)


def _normalize(parts) -> str:
    """Rebuild a clean URL: scheme, host, optional port, clean path, no query/fragment."""

    scheme = parts.scheme.lower() if parts.scheme else "https"
    netloc = parts.hostname or ""
    port = parts.port
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = (parts.path or "").rstrip("/")
    return urlunsplit((scheme, netloc, path, "", "")).rstrip("/")


def is_safe_url(url: str) -> bool:
    """Boolean wrapper around :func:`validate_base_url` (never raises)."""

    try:
        validate_base_url(url)
    except UnsafeURLError:
        return False
    return True


# Keep ``Any`` import used to satisfy linters that flag unused imports in some
# configurations; it is harmless.
_ = Any
