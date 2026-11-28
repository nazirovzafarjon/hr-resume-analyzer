"""Regression tests: bot button plumbing and completing an AI batch exactly once.

* ``handlers._answer`` once called itself instead of ``query.answer()``: every
  button press ended in a ``RecursionError`` and the spinner never stopped.
  The handler layer had no tests, so these drive it with stand-in objects.
* Two batch-item workers finishing together could both mark the batch
  completed and both queue the Telegram summary.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.bot import actions, handlers
from app.core.config import settings
from app.core.database import SessionLocal
from app.crud import batch as batch_crud
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from tests.test_telegram_hr_notifications import HR_TG, _add_application, _create_job, _link_hr


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=MagicMock(), message=message)


def _query(data: str = "hr:new:0", language: str = "uz") -> MagicMock:
    """A callback query from HR_TG in a private chat, with awaitable methods."""
    user = MagicMock(id=HR_TG, username="hr", first_name="Hana", language_code=language)
    query = MagicMock(data=data, from_user=user)
    query.answer = AsyncMock()
    query.message.chat.id = HR_TG
    query.message.edit_text = AsyncMock()
    query.message.answer = AsyncMock()
    query.message.answer_document = AsyncMock()
    return query


def _state() -> MagicMock:
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    return state


# --- callback plumbing ---------------------------------------------------------------


def test_answer_stops_the_spinner_once():
    query = _query()
    asyncio.run(handlers._answer(query))
    query.answer.assert_awaited_once_with()


def test_answer_ignores_an_expired_query():
    query = _query()
    query.answer.side_effect = _bad_request("query is too old and response timeout expired")
    asyncio.run(handlers._answer(query))
    query.answer.assert_awaited_once()


def test_show_edits_the_message_and_answers():
    query = _query()
    reply = actions.Reply("hello", [[{"text": "A", "callback_data": "x"}]])
    asyncio.run(handlers._show(query, reply))
    query.message.edit_text.assert_awaited_once()
    assert query.message.edit_text.await_args.args[0] == "hello"
    query.message.answer.assert_not_awaited()
    query.answer.assert_awaited_once()


def test_show_does_not_resend_an_unchanged_message():
    query = _query()
    query.message.edit_text.side_effect = _bad_request("message is not modified")
    asyncio.run(handlers._show(query, actions.Reply("same")))
    query.message.answer.assert_not_awaited()
    query.answer.assert_awaited_once()


def test_show_sends_anew_when_the_message_cannot_be_edited():
    query = _query()
    query.message.edit_text.side_effect = _bad_request("message can't be edited")
    asyncio.run(handlers._show(query, actions.Reply("fresh")))
    query.message.answer.assert_awaited_once()
    assert query.message.answer.await_args.args[0] == "fresh"
    query.answer.assert_awaited_once()


def test_send_falls_back_when_the_document_fails(tmp_path):
    query = _query()
    query.message.answer_document.side_effect = _bad_request("file is too big")
    path = tmp_path / "cv.pdf"
    path.write_bytes(b"%PDF")
    asyncio.run(handlers._send(query, actions.Reply("cv", document=(str(path), "cv.pdf"))))
    query.message.answer.assert_awaited_once()
    assert "Rezyume" in query.message.answer.await_args.args[0]
    query.answer.assert_awaited_once()


def test_unknown_hr_action_only_stops_the_spinner():
    query = _query("hr:nope:1")
    asyncio.run(handlers.on_hr_callback(query, _state()))
    query.message.edit_text.assert_not_awaited()
    query.answer.assert_awaited_once()


def test_hr_list_button_end_to_end(user, client):
    _link_hr(user["id"])
    job = _create_job(client, user["headers"])
    _add_application(job["id"], name="Jane Doe")
    query = _query("hr:ls:new:0:0")
    state = _state()

    asyncio.run(handlers.on_hr_callback(query, state))

    text = query.message.edit_text.await_args.args[0]
    assert "Jane Doe" in text and "Arizalar" in text
    state.update_data.assert_awaited_once_with(hr_list=["ls", "new", 0])
    query.answer.assert_awaited_once()


# --- batch completion ----------------------------------------------------------------


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")


@pytest.fixture
def sent(monkeypatch):
    from app.services.telegram import client as tg_client

    messages: list[dict] = []

    def fake_send(chat_id, text, *, buttons=None):
        messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": len(messages)}

    monkeypatch.setattr(tg_client, "send_message", fake_send)
    return messages


def test_parallel_finishers_complete_the_batch_once(client, user, telegram_on, sent):
    _link_hr(user["id"])
    job = _create_job(client, user["headers"])
    ids = [_add_application(job["id"], name=f"P{n}") for n in range(2)]
    with SessionLocal() as db:
        batch = batch_crud.create_batch(db, owner_id=user["id"], application_ids=ids)
        batch.status = AnalysisBatchStatus.RUNNING
        batch.successful_count = 2
        db.commit()
        batch_id = batch.id

    # Worker A read the batch (still RUNNING) before worker B completed it.
    # Keep the reference: the identity map is weak, and this stale object is
    # exactly what an unlocked re-read in worker A would get back.
    worker_a = SessionLocal()
    try:
        stale = worker_a.get(AnalysisBatch, batch_id)
        assert stale.status == AnalysisBatchStatus.RUNNING
        with SessionLocal() as worker_b:
            assert batch_crud.check_and_complete_batch(worker_b, batch_id) is True
        assert batch_crud.check_and_complete_batch(worker_a, batch_id) is True
    finally:
        worker_a.close()

    summaries = [m for m in sent if "Jami: 2" in m["text"]]
    assert len(summaries) == 1


def test_unfinished_batch_releases_its_lock(client, user):
    job = _create_job(client, user["headers"])
    ids = [_add_application(job["id"], name=f"P{n}") for n in range(2)]
    with SessionLocal() as db:
        batch = batch_crud.create_batch(db, owner_id=user["id"], application_ids=ids)
        batch_id = batch.id
        assert batch_crud.check_and_complete_batch(db, batch_id) is False
        # The lock is gone: another session can lock the row without waiting.
        with SessionLocal() as other:
            other.execute(
                AnalysisBatch.__table__.select()
                .where(AnalysisBatch.id == batch_id)
                .with_for_update(nowait=True)
            )
            other.rollback()
