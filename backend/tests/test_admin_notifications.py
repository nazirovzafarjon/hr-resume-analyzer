"""Tests for superuser admin notifications (Contact Us inquiries) management."""

import pytest

from app.models.contact_message import ContactMessage

BASE_URL = "/api/admin/notifications"
PUBLIC_CONTACT_URL = "/api/public/contact"


def _seed_messages(db_session, count=5) -> list[ContactMessage]:
    """Helper to seed test contact messages directly into database."""
    messages = []
    for i in range(count):
        msg = ContactMessage(
            first_name=f"User{i}",
            last_name=f"Test{i}",
            email=f"user{i}@example.com",
            subject=f"Inquiry Subject {i}" if i % 2 == 0 else None,
            message=f"This is test message {i} with some content.",
            is_read=(i >= 3),  # 0, 1, 2 unread, 3, 4 read
        )
        db_session.add(msg)
    db_session.commit()
    for msg in messages:
        db_session.refresh(msg)
    return messages


class TestAdminNotificationsAuth:
    def test_anonymous_request_is_rejected(self, client):
        res = client.get(BASE_URL)
        assert res.status_code == 401

    def test_regular_hr_user_is_forbidden(self, client, user):
        res = client.get(BASE_URL, headers=user["headers"])
        assert res.status_code == 403

    def test_admin_can_access_notifications(self, client, admin):
        res = client.get(BASE_URL, headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "unread_count" in data


class TestListNotifications:
    def test_empty_listing(self, client, admin):
        res = client.get(BASE_URL, headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    def test_listing_with_trailing_slash(self, client, admin):
        res = client.get(f"{BASE_URL}/", headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []

    def test_listing_with_seed_data(self, client, admin, db_session):
        _seed_messages(db_session, count=6)
        res = client.get(BASE_URL, headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 6
        assert data["unread_count"] == 3
        assert len(data["items"]) == 6

        first = data["items"][0]
        assert "id" in first
        assert "name" in first
        assert "email" in first
        assert "message" in first
        assert "is_read" in first
        assert "created_at" in first

    def test_filter_by_is_read_status(self, client, admin, db_session):
        _seed_messages(db_session, count=5)  # 3 unread, 2 read

        # Filter unread
        res_unread = client.get(f"{BASE_URL}?is_read=false", headers=admin["headers"])
        assert res_unread.status_code == 200
        data_unread = res_unread.json()
        assert data_unread["total"] == 3
        assert all(item["is_read"] is False for item in data_unread["items"])

        # Filter read
        res_read = client.get(f"{BASE_URL}?is_read=true", headers=admin["headers"])
        assert res_read.status_code == 200
        data_read = res_read.json()
        assert data_read["total"] == 2
        assert all(item["is_read"] is True for item in data_read["items"])

    def test_search_filter(self, client, admin, db_session):
        _seed_messages(db_session, count=4)
        msg_custom = ContactMessage(
            first_name="Leonardo",
            last_name="DaVinci",
            email="monalisa@renaissance.art",
            subject="Masterpiece feedback",
            message="Unique artwork question here",
            is_read=False,
        )
        db_session.add(msg_custom)
        db_session.commit()

        # Search by email
        res = client.get(f"{BASE_URL}?q=monalisa", headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "monalisa@renaissance.art"

        # Search by message snippet
        res2 = client.get(f"{BASE_URL}?q=Unique+artwork", headers=admin["headers"])
        assert res2.status_code == 200
        assert res2.json()["total"] == 1

    def test_pagination(self, client, admin, db_session):
        _seed_messages(db_session, count=10)
        res = client.get(f"{BASE_URL}?page=1&limit=3", headers=admin["headers"])
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["limit"] == 3

        res_p2 = client.get(f"{BASE_URL}?page=2&limit=3", headers=admin["headers"])
        assert res_p2.status_code == 200
        data_p2 = res_p2.json()
        assert len(data_p2["items"]) == 3
        assert data_p2["page"] == 2
        # Verify different items
        p1_ids = {item["id"] for item in data["items"]}
        p2_ids = {item["id"] for item in data_p2["items"]}
        assert p1_ids.isdisjoint(p2_ids)


class TestUnreadCountEndpoint:
    def test_unread_count(self, client, admin, db_session):
        _seed_messages(db_session, count=5)  # 3 unread
        res = client.get(f"{BASE_URL}/unread-count", headers=admin["headers"])
        assert res.status_code == 200
        assert res.json() == {"unread_count": 3}

    def test_unread_count_with_trailing_slash(self, client, admin, db_session):
        _seed_messages(db_session, count=5)  # 3 unread
        res = client.get(f"{BASE_URL}/unread-count/", headers=admin["headers"])
        assert res.status_code == 200
        assert res.json() == {"unread_count": 3}


class TestMarkNotificationRead:
    def test_mark_as_read(self, client, admin, db_session):
        msg = ContactMessage(
            first_name="Marie",
            last_name="Curie",
            email="marie@radium.org",
            message="Radioactivity inquiry",
            is_read=False,
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)

        res = client.patch(f"{BASE_URL}/{msg.id}/read", headers=admin["headers"])
        assert res.status_code == 200
        assert res.json()["is_read"] is True

        db_session.refresh(msg)
        assert msg.is_read is True

    def test_toggle_back_to_unread(self, client, admin, db_session):
        msg = ContactMessage(
            first_name="Nikola",
            last_name="Tesla",
            email="nikola@ac.net",
            message="Alternating current",
            is_read=True,
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)

        res = client.patch(
            f"{BASE_URL}/{msg.id}/read",
            json={"is_read": False},
            headers=admin["headers"],
        )
        assert res.status_code == 200
        assert res.json()["is_read"] is False

        db_session.refresh(msg)
        assert msg.is_read is False

    def test_mark_nonexistent_returns_404(self, client, admin):
        res = client.patch(f"{BASE_URL}/99999/read", headers=admin["headers"])
        assert res.status_code == 404


class TestDeleteNotification:
    def test_delete_notification(self, client, admin, db_session):
        msg = ContactMessage(
            first_name="Alan",
            last_name="Turing",
            email="alan@enigma.gov",
            message="Turing machine specs",
            is_read=False,
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)

        res = client.delete(f"{BASE_URL}/{msg.id}", headers=admin["headers"])
        assert res.status_code == 204

        assert db_session.query(ContactMessage).filter(ContactMessage.id == msg.id).first() is None

    def test_delete_nonexistent_returns_404(self, client, admin):
        res = client.delete(f"{BASE_URL}/99999", headers=admin["headers"])
        assert res.status_code == 404
