"""Live updates for the support chat: Redis pub/sub fanned out over SSE.

Every API worker can serve any browser, so a message saved by one worker has
to reach streams held open by the others. The worker that saves a change
publishes a tiny event on Redis; each open Server-Sent Events stream is
subscribed to the channels its viewer may see and forwards the event.

Events carry only ``{"type", "conversation_id"}``. The browser then reloads
the conversation through the normal authenticated REST endpoints, so the
stream never carries message text and needs no authorization rules of its own
beyond choosing the channels.

Channels:

* ``support:admin``            every support event (admins only),
* ``support:hr:<user id>``     events for one HR user's conversations,
* ``support:candidate:<id>``   events for one candidate's conversations.

Publishing is best effort: if Redis is down the change is still saved, and the
browser picks it up on its periodic refresh.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Iterable

import redis.asyncio as aioredis
from starlette.requests import Request

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

ADMIN_CHANNEL = "support:admin"

#: Seconds between keep-alive comments, so proxies do not drop an idle stream.
HEARTBEAT_SECONDS = 20.0
#: How long one stream stays open before the browser is asked to reconnect.
#: Bounds the life of a stream whose client vanished without a disconnect.
MAX_STREAM_SECONDS = 15 * 60

#: Headers that keep nginx and browsers from buffering or caching the stream.
STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def requester_channel(kind: str, requester_id: int) -> str:
    return f"support:{kind}:{requester_id}"


def publish(event_type: str, conversation_id: int, channels: Iterable[str]) -> None:
    """Tell open streams that a conversation changed. Never raises."""
    payload = json.dumps({"type": event_type, "conversation_id": conversation_id})
    try:
        client = get_redis_client()
        for channel in channels:
            client.publish(channel, payload)
    except Exception as exc:  # noqa: BLE001 -- live updates must never break a save
        logger.warning("Support event not published (%s): %s", event_type, exc)


async def event_stream(request: Request, channels: list[str]) -> AsyncIterator[str]:
    """Yield SSE frames for ``channels`` until the client leaves or time runs out."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    try:
        try:
            await pubsub.subscribe(*channels)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Support stream could not subscribe: %s", exc)
            # Tell the browser to fall back to polling for a while.
            yield "retry: 30000\nevent: unavailable\ndata: {}\n\n"
            return

        yield "retry: 5000\nevent: ready\ndata: {}\n\n"
        started = last_beat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            now = time.monotonic()
            if now - started >= MAX_STREAM_SECONDS:
                return
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Support stream lost Redis: %s", exc)
                return
            if message and message.get("type") == "message":
                yield f"event: support\ndata: {message['data']}\n\n"
            elif message is None:
                # get_message may return at once with nothing; avoid a busy loop.
                await asyncio.sleep(0.05)
            if time.monotonic() - last_beat >= HEARTBEAT_SECONDS:
                last_beat = time.monotonic()
                yield ": ping\n\n"
    finally:
        try:
            await pubsub.aclose()
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
