"""Help Center support chat: requester and admin APIs, ownership, closing, live events."""

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import create_candidate_email_verification_token
from app.models.audit_log import AuditLog
from app.services import support as support_service
from app.services import support_realtime

HR = "/api/support"
CANDIDATE = "/api/candidate/support"
ADMIN = "/api/admin/support"


@pytest.fixture(autouse=True)
def events(monkeypatch):
    """Capture live-update events instead of publishing them to Redis."""
    published: list[tuple[str, int, list[str]]] = []

    def fake_publish(event_type, conversation_id, channels):
        published.append((event_type, conversation_id, list(channels)))

    monkeypatch.setattr(support_realtime, "publish", fake_publish)
    support_service.reset_rate_limits()
    yield published
    support_service.reset_rate_limits()


def _candidate(client, email="jane@example.com"):
    response = client.post(
        "/api/candidate/auth/register",
        json={"email": email, "full_name": "Jane Candidate", "password": "CandidatePass1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    token = create_candidate_email_verification_token(body["candidate"]["id"])
    client.post("/api/candidate/auth/verify-email", json={"token": token})
    return {
        "id": body["candidate"]["id"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


def _open(client, base, headers, body="I cannot upload my resume", page_url="/jobs"):
    response = client.post(
        f"{base}/conversations", json={"body": body, "page_url": page_url}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Requester side
# ---------------------------------------------------------------------------


def test_hr_opens_a_conversation_and_admins_are_notified(client, user, admin, events):
    conversation = _open(client, HR, user["headers"])

    assert conversation["status"] == "open"
    assert [m["sender"] for m in conversation["messages"]] == ["requester"]
    assert conversation["messages"][0]["body"] == "I cannot upload my resume"
    assert events == [
        ("conversation", conversation["id"], ["support:admin", f"support:hr:{user['id']}"])
    ]

    inbox = client.get(f"{ADMIN}/conversations", headers=admin["headers"]).json()
    assert inbox["total"] == 1
    row = inbox["items"][0]
    assert row["requester_kind"] == "hr"
    assert row["requester_email"] == user["email"]
    assert row["unread_count"] == 1
    assert row["preview"] == "I cannot upload my resume"
    assert client.get(f"{ADMIN}/unread-count", headers=admin["headers"]).json() == {"unread_count": 1}


def test_only_one_open_conversation_at_a_time(client, user):
    _open(client, HR, user["headers"])
    response = client.post(f"{HR}/conversations", json={"body": "again"}, headers=user["headers"])
    assert response.status_code == 409


def test_blank_message_is_rejected(client, user):
    response = client.post(f"{HR}/conversations", json={"body": "   "}, headers=user["headers"])
    assert response.status_code == 422


def test_reply_round_trip_and_unread_counts(client, user, admin):
    conversation = _open(client, HR, user["headers"])
    cid = conversation["id"]

    detail = client.get(f"{ADMIN}/conversations/{cid}", headers=admin["headers"]).json()
    assert detail["page_url"] == "/jobs"
    assert client.get(f"{ADMIN}/unread-count", headers=admin["headers"]).json()["unread_count"] == 0

    reply = client.post(
        f"{ADMIN}/conversations/{cid}/messages",
        json={"body": "Please try a PDF under 10 MB"},
        headers=admin["headers"],
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["messages"][-1]["author_name"] == "Administrator"

    assert client.get(f"{HR}/unread-count", headers=user["headers"]).json()["unread_count"] == 1
    listing = client.get(f"{HR}/conversations", headers=user["headers"]).json()
    assert listing[0]["unread_count"] == 1

    opened = client.get(f"{HR}/conversations/{cid}", headers=user["headers"]).json()
    assert [m["sender"] for m in opened["messages"]] == ["requester", "admin"]
    assert client.get(f"{HR}/unread-count", headers=user["headers"]).json()["unread_count"] == 0

    follow_up = client.post(
        f"{HR}/conversations/{cid}/messages", json={"body": "That worked, thanks"}, headers=user["headers"]
    )
    assert follow_up.status_code == 201
    assert client.get(f"{ADMIN}/unread-count", headers=admin["headers"]).json()["unread_count"] == 1


def test_closed_conversation_is_read_only_and_a_new_one_can_start(client, user, admin, events):
    cid = _open(client, HR, user["headers"])["id"]

    closed = client.post(f"{ADMIN}/conversations/{cid}/close", headers=admin["headers"])
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_by_name"] == "Administrator"
    assert ("closed", cid, ["support:admin", f"support:hr:{user['id']}"]) in events

    assert (
        client.post(f"{HR}/conversations/{cid}/messages", json={"body": "hi"}, headers=user["headers"]).status_code
        == 409
    )
    assert (
        client.post(f"{ADMIN}/conversations/{cid}/messages", json={"body": "hi"}, headers=admin["headers"]).status_code
        == 409
    )
    # Closing twice is harmless.
    assert client.post(f"{ADMIN}/conversations/{cid}/close", headers=admin["headers"]).status_code == 200

    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.action == "SUPPORT_CLOSED")).all()
        assert [r.resource_id for r in rows] == [str(cid)]

    fresh = _open(client, HR, user["headers"], body="New problem")
    assert fresh["id"] != cid
    assert client.get(f"{ADMIN}/conversations?status=open", headers=admin["headers"]).json()["total"] == 1
    assert client.get(f"{ADMIN}/conversations?status=closed", headers=admin["headers"]).json()["total"] == 1


def test_requesters_only_reach_their_own_conversations(client, user, other_user):
    cid = _open(client, HR, user["headers"])["id"]

    assert client.get(f"{HR}/conversations/{cid}", headers=other_user["headers"]).status_code == 404
    assert (
        client.post(
            f"{HR}/conversations/{cid}/messages", json={"body": "x"}, headers=other_user["headers"]
        ).status_code
        == 404
    )
    assert client.get(f"{HR}/conversations", headers=other_user["headers"]).json() == []


def test_candidate_conversation_is_separate_from_hr(client, user, admin, events):
    candidate = _candidate(client)
    conversation = _open(client, CANDIDATE, candidate["headers"], body="Where is my interview link?")
    assert events[-1] == (
        "conversation",
        conversation["id"],
        ["support:admin", f"support:candidate:{candidate['id']}"],
    )

    # The candidate's id must not be reachable through the HR API, and the
    # two token kinds are not interchangeable.
    assert client.get(f"{HR}/conversations/{conversation['id']}", headers=user["headers"]).status_code == 404
    assert client.get(f"{HR}/conversations", headers=candidate["headers"]).status_code == 401
    assert client.get(f"{CANDIDATE}/conversations", headers=user["headers"]).status_code == 401

    rows = client.get(f"{ADMIN}/conversations?kind=candidate", headers=admin["headers"]).json()["items"]
    assert [r["requester_name"] for r in rows] == ["Jane Candidate"]
    assert client.get(f"{ADMIN}/conversations?kind=hr", headers=admin["headers"]).json()["total"] == 0


def test_admin_search_matches_people_and_message_text(client, user, admin):
    _open(client, HR, user["headers"], body="Export to Excel is broken")
    candidate = _candidate(client, email="maria@example.com")
    _open(client, CANDIDATE, candidate["headers"], body="Password reset email never came")

    def search(q):
        return [r["requester_email"] for r in client.get(
            f"{ADMIN}/conversations", params={"q": q}, headers=admin["headers"]
        ).json()["items"]]

    assert search("excel") == [user["email"]]
    assert search("maria@") == ["maria@example.com"]
    assert sorted(search("e")) == sorted([user["email"], "maria@example.com"])


def test_sending_too_fast_is_rate_limited(client, user):
    cid = _open(client, HR, user["headers"])["id"]
    statuses = [
        client.post(f"{HR}/conversations/{cid}/messages", json={"body": f"m{i}"}, headers=user["headers"]).status_code
        for i in range(21)
    ]
    assert statuses[-1] == 429
    assert statuses.count(201) == 19  # the opening message counted too


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", f"{ADMIN}/conversations"),
        ("get", f"{ADMIN}/unread-count"),
        ("get", f"{ADMIN}/conversations/1"),
        ("post", f"{ADMIN}/conversations/1/close"),
    ],
)
def test_admin_inbox_requires_an_admin_session(client, user, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers=user["headers"]).status_code == 403


def test_requester_routes_require_sign_in(client):
    assert client.get(f"{HR}/conversations").status_code == 401
    assert client.get(f"{CANDIDATE}/conversations").status_code == 401


def test_unknown_conversation_is_404_for_admins(client, admin):
    assert client.get(f"{ADMIN}/conversations/999", headers=admin["headers"]).status_code == 404


# ---------------------------------------------------------------------------
# Live stream
# ---------------------------------------------------------------------------


@pytest.fixture
def finite_stream(monkeypatch):
    """Replace the Redis-backed stream with one frame naming its channels."""

    async def one_frame(request, channels):
        yield f"event: ready\ndata: {','.join(channels)}\n\n"

    monkeypatch.setattr(support_realtime, "event_stream", one_frame)


def test_streams_subscribe_to_the_callers_channels(client, user, admin, finite_stream):
    hr = client.get(f"{HR}/stream", headers=user["headers"])
    assert hr.status_code == 200
    assert hr.headers["content-type"].startswith("text/event-stream")
    assert hr.headers["x-accel-buffering"] == "no"
    assert f"support:hr:{user['id']}" in hr.text

    candidate = _candidate(client)
    response = client.get(f"{CANDIDATE}/stream", headers=candidate["headers"])
    assert f"support:candidate:{candidate['id']}" in response.text

    assert "support:admin" in client.get(f"{ADMIN}/stream", headers=admin["headers"]).text


def test_streams_reject_the_wrong_caller(client, user, finite_stream):
    assert client.get(f"{HR}/stream").status_code == 401
    assert client.get(f"{CANDIDATE}/stream", headers=user["headers"]).status_code == 401
    assert client.get(f"{ADMIN}/stream").status_code == 401
    assert client.get(f"{ADMIN}/stream", headers=user["headers"]).status_code == 403
