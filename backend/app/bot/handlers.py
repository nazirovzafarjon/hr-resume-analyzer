"""aiogram handlers: private-chat commands mapped onto ``app.bot.actions``."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot import actions
from app.bot.texts import t
from app.services.telegram.linking import TelegramProfile

logger = logging.getLogger(__name__)

router = Router(name="linking")
# Account data is personal: the bot only answers in one-to-one chats.
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


def _profile(message: Message, user=None) -> TelegramProfile:
    user = user or message.from_user
    return TelegramProfile(
        telegram_user_id=user.id,
        chat_id=message.chat.id,
        username=user.username,
        first_name=user.first_name,
        language_code=user.language_code,
    )


async def _reply(message: Message, action: Callable[..., str], *args) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    try:
        text = await asyncio.to_thread(action, profile, *args)
    except Exception:  # noqa: BLE001 -- never leave the user without an answer
        logger.exception("Bot command failed")
        text = t(profile.language_code, "error")
    await message.answer(text, disable_web_page_preview=True)


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject) -> None:
    await _reply(message, actions.start, command.args)


@router.message(Command("status"))
async def on_status(message: Message) -> None:
    await _reply(message, actions.status)


@router.message(Command("unlink"))
async def on_unlink(message: Message) -> None:
    await _reply(message, actions.unlink)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await _reply(message, actions.help_text)


@router.message(Command("applications"))
async def on_applications(message: Message) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    reply = await _run(profile, actions.applications_page, profile, 0)
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("apps:") | F.data.startswith("app:"))
async def on_application_callback(query: CallbackQuery) -> None:
    """List pages (``apps:<page>``) and cards (``app:<id>:<page>``) edit the message in place."""
    if query.message is None:
        await query.answer()
        return
    profile = _profile(query.message, query.from_user)
    try:
        parts = query.data.split(":")
        if parts[0] == "apps":
            reply = await _run(profile, actions.applications_page, profile, int(parts[1]))
        else:
            reply = await _run(profile, actions.application_detail, profile, int(parts[1]), int(parts[2]))
    except (IndexError, ValueError):
        await query.answer()
        return
    await _show(query, reply)


@router.message(Command("new"))
async def on_new(message: Message) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    reply = await _run(profile, actions.hr_new_page, profile, 0)
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.message(Command("settings"))
async def on_settings(message: Message) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    reply = await _run(profile, actions.settings_page, profile)
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("cfg:"))
async def on_settings_callback(query: CallbackQuery) -> None:
    """``cfg:<kind>:<key>`` flips one notification switch of this user's own link."""
    if query.message is None:
        await query.answer()
        return
    profile = _profile(query.message, query.from_user)
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    reply = await _run(profile, actions.toggle_setting, profile, parts[1], parts[2])
    await _show(query, reply)


class MeetingLink(StatesGroup):
    """Waiting for the meeting link of ``interview_id`` (kept in the FSM data).

    The default in-memory FSM storage is enough: the bot runs as one process,
    and a restart only means the HR user taps "add link" again.
    """

    waiting = State()


@router.message(Command("cancel"))
async def on_cancel(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    waiting = await state.get_state()
    await state.clear()
    key = "cancelled" if waiting else "nothing_to_cancel"
    await message.answer(t(message.from_user.language_code, key))


@router.message(MeetingLink.waiting, F.text, ~F.text.startswith("/"))
async def on_meeting_link(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    data = await state.get_data()
    reply = await _run(
        profile, actions.hr_set_meeting_link, profile, int(data["interview_id"]), message.text, int(data["page"])
    )
    if not reply.awaiting_input:
        await state.clear()
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("hr:"))
async def on_hr_callback(query: CallbackQuery, state: FSMContext) -> None:
    """HR callbacks.

    * ``hr:new:<page>`` -- page of unreviewed applications
    * ``hr:app:<id>:<page>`` -- one application's card
    * ``hr:set:<id>:<status>:<page>`` -- change the status (final decisions ask first)
    * ``hr:ok:<id>:<status>:<page>`` -- confirmed final decision
    * ``hr:iv:<id>:<page>`` -- schedule an interview: pick a day
    * ``hr:ivd:<id>:<YYYYMMDD>:<page>`` -- pick a time on that day
    * ``hr:ivt:<id>:<YYYYMMDDHHMM>:<minutes>:<page>`` -- review, choose the duration
    * ``hr:ivok:<id>:<YYYYMMDDHHMM>:<minutes>:<page>`` -- create the interview
    * ``hr:ivlink:<interview id>:<page>`` -- ask for the meeting link
    * ``hr:rs`` / ``hr:rsd`` / ``hr:rst`` / ``hr:rsok`` -- the same steps to
      reschedule, keyed by the interview id
    * ``hr:ivx:<interview id>:<page>`` -- ask before cancelling an interview
    * ``hr:ivxok:<interview id>:<page>`` -- cancel it
    """
    if query.message is None:
        await query.answer()
        return
    profile = _profile(query.message, query.from_user)
    # Any other button abandons a pending meeting-link question.
    await state.clear()
    try:
        parts = query.data.split(":")
        if parts[1] == "iv":
            reply = await _run(profile, actions.hr_schedule_days, profile, int(parts[2]), int(parts[3]))
        elif parts[1] == "ivd":
            reply = await _run(profile, actions.hr_schedule_times, profile, int(parts[2]), parts[3], int(parts[4]))
        elif parts[1] in ("ivt", "ivok"):
            step = actions.hr_schedule_review if parts[1] == "ivt" else actions.hr_schedule_confirm
            reply = await _run(profile, step, profile, int(parts[2]), parts[3], int(parts[4]), int(parts[5]))
        elif parts[1] == "rs":
            reply = await _run(profile, actions.hr_reschedule_days, profile, int(parts[2]), int(parts[3]))
        elif parts[1] == "rsd":
            reply = await _run(profile, actions.hr_reschedule_times, profile, int(parts[2]), parts[3], int(parts[4]))
        elif parts[1] in ("rst", "rsok"):
            step = actions.hr_reschedule_review if parts[1] == "rst" else actions.hr_reschedule_confirm
            reply = await _run(profile, step, profile, int(parts[2]), parts[3], int(parts[4]), int(parts[5]))
        elif parts[1] in ("ivx", "ivxok"):
            reply = await _run(
                profile,
                partial(actions.hr_cancel_interview, confirmed=parts[1] == "ivxok"),
                profile,
                int(parts[2]),
                int(parts[3]),
            )
        elif parts[1] == "ivlink":
            interview_id, page = int(parts[2]), int(parts[3])
            reply = await _run(profile, actions.hr_meeting_link_prompt, profile, interview_id, page)
            if reply.awaiting_input:
                await state.set_state(MeetingLink.waiting)
                await state.update_data(interview_id=interview_id, page=page)
                # Keep the card; ask in a new message the answer goes under.
                await query.message.answer(reply.text)
                await query.answer()
                return
        elif parts[1] == "new":
            reply = await _run(profile, actions.hr_new_page, profile, int(parts[2]))
        elif parts[1] == "app":
            reply = await _run(profile, actions.hr_application_detail, profile, int(parts[2]), int(parts[3]))
        elif parts[1] in ("set", "ok"):
            reply = await _run(
                profile,
                partial(actions.hr_set_status, confirmed=parts[1] == "ok"),
                profile,
                int(parts[2]),
                parts[3],
                int(parts[4]),
            )
        else:
            raise ValueError(parts[1])
    except (IndexError, ValueError):
        await query.answer()
        return
    await _show(query, reply)


async def _show(query: CallbackQuery, reply: "actions.Reply") -> None:
    try:
        await query.message.edit_text(
            reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True
        )
    except TelegramBadRequest:
        # "message is not modified" (same page pressed twice) or a message too
        # old to edit: send the content as a new message instead.
        await query.message.answer(reply.text, reply_markup=_keyboard(reply.buttons))
    await query.answer()


async def _run(profile: TelegramProfile, action, *args) -> "actions.Reply":
    try:
        return await asyncio.to_thread(action, *args)
    except Exception:  # noqa: BLE001 -- never leave the user without an answer
        logger.exception("Bot action failed")
        return actions.Reply(t(profile.language_code, "error"))


def _keyboard(rows: list[list[dict[str, str]]]) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(**button) for button in row] for row in rows]
    )
