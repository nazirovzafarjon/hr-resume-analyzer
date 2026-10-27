"""A tiny in-process rate limiter for unauthenticated abuse-prone actions.

Email-verification resend is public (an unverified user usually has no usable
panel session), so it needs a guard that does not depend on Redis. This mirrors
the Contact-form limiter in ``app.services.contact_message``: state lives in the
worker's memory, a restart resets it, and each uvicorn worker keeps its own
count. That is enough to stop a stuck button or a naive script.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Allow at most ``max_events`` per ``window_seconds`` for each key."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = {}

    def check(self, key: str) -> bool:
        """Record an event for ``key``; return ``False`` when over the limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            # Drop idle keys so the map cannot grow without bound.
            for stale in [k for k, stamps in self._events.items() if not stamps or stamps[-1] < cutoff]:
                del self._events[stale]
            stamps = self._events.setdefault(key, deque())
            while stamps and stamps[0] < cutoff:
                stamps.popleft()
            if len(stamps) >= self.max_events:
                return False
            stamps.append(now)
            return True

    def retry_after(self, key: str) -> float:
        """Seconds until ``key`` may act again (0 when it may act now)."""
        now = time.monotonic()
        with self._lock:
            stamps = self._events.get(key)
            if not stamps:
                return 0.0
            remaining = self.window_seconds - (now - stamps[-1])
            return max(0.0, remaining)

    def reset(self) -> None:
        """Forget every recorded event (used by the test suite)."""
        with self._lock:
            self._events.clear()
