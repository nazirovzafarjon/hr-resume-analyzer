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
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
async def on_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    """Link with a token, or show the home screen with quick-action buttons."""
    if message.from_user is None:
        return
    await state.set_state(None)
    profile = _profile(message)
    try:
        text = await asyncio.to_thread(actions.start, profile, command.args)
        buttons = await asyncio.to_thread(actions.home_buttons, profile)
    except Exception:  # noqa: BLE001 -- never leave the user without an answer
        logger.exception("Bot /start failed")
        text, buttons = t(profile.language_code, "error"), []
    await message.answer(text, reply_markup=_keyboard(buttons), disable_web_page_preview=True)


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
async def on_applications(message: Message, state: FSMContext) -> None:
    """HR users get the filtered HR list (phase 8), candidates their own list."""
    if message.from_user is None:
        return
    profile = _profile(message)
    await _remember_list(state, ["ls", "all", 0])
    reply = await _run(profile, actions.applications_entry, profile)
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("apps:") | F.data.startswith("app:"))
async def on_application_callback(query: CallbackQuery) -> None:
    """List pages (``apps:<page>``) and cards (``app:<id>:<page>``) edit the message in place."""
    if query.message is None:
        await _answer(query)
        return
    profile = _profile(query.message, query.from_user)
    try:
        parts = query.data.split(":")
        if parts[0] == "apps":
            reply = await _run(profile, actions.applications_page, profile, int(parts[1]))
        else:
            reply = await _run(profile, actions.application_detail, profile, int(parts[1]), int(parts[2]))
    except (IndexError, ValueError):
        await _answer(query)
        return
    await _show(query, reply)


@router.message(Command("new"))
async def on_new(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    await _remember_list(state, ["ls", "new", 0])
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
        await _answer(query)
        return
    profile = _profile(query.message, query.from_user)
    parts = query.data.split(":")
    if parts == ["cfg", "open"]:
        # The "Settings" button of the /start home screen.
        reply = await _run(profile, actions.settings_page, profile)
    elif len(parts) == 3:
        reply = await _run(profile, actions.toggle_setting, profile, parts[1], parts[2])
    else:
        await _answer(query)
        return
    await _show(query, reply)


class MeetingLink(StatesGroup):
    """Waiting for the meeting link of ``interview_id`` (kept in the FSM data).

    The default in-memory FSM storage is enough: the bot runs as one process,
    and a restart only means the HR user taps "add link" again.
    """

    waiting = State()


class Search(StatesGroup):
    """Waiting for the text to search applications by (phase 8)."""

    waiting = State()


async def _remember_list(state: FSMContext, context: list) -> None:
    """Remember the list a card is opened from, for its "back" button.

    Kept in the FSM data (in memory): after a bot restart "back" falls back
    to the unreviewed applications.
    """
    await state.update_data(hr_list=context)


@router.message(Command("cancel"))
async def on_cancel(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    waiting = await state.get_state()
    await state.set_state(None)
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
        await state.set_state(None)
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


@router.message(Search.waiting, F.text, ~F.text.startswith("/"))
async def on_search_text(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    profile = _profile(message)
    reply = await _run(profile, actions.hr_search, profile, message.text, 0)
    if not reply.awaiting_input:
        await state.set_state(None)
        await _remember_list(state, ["sr", message.text])
    await message.answer(reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True)


async def _list_reply(profile: TelegramProfile, context, page: int) -> "actions.Reply":
    """Re-open a remembered list (``["ls", filter, job]`` or ``["sr", text]``)."""
    if context and context[0] == "sr":
        return await _run(profile, actions.hr_search, profile, context[1], page)
    if context and context[0] == "ls":
        return await _run(profile, actions.hr_list, profile, context[1], int(context[2]), page)
    return await _run(profile, actions.hr_new_page, profile, page)


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
    * ``hr:ls:<filter>:<job id or 0>:<page>`` -- filtered list (phase 8)
    * ``hr:sr:<page>`` -- page of the last search; ``hr:find`` -- ask for one
    * ``hr:back:<page>`` -- back to the list the card was opened from
    * ``hr:jobs:<filter>`` -- pick a job to narrow the list to
    * ``hr:cv`` / ``hr:fa`` / ``hr:aix:<id>:<page>`` -- resume file, form answers, AI summary
    * ``hr:ai`` / ``hr:air:<id>:<page>`` -- start (or re-run) the AI analysis
    * ``hr:aiall`` / ``hr:aiallok:<job id or 0>`` -- analyse the new ones (asks first)
    """
    if query.message is None:
        await _answer(query)
        return
    profile = _profile(query.message, query.from_user)
    # Any other button abandons a pending meeting-link or search question
    # (the remembered list stays).
    await state.set_state(None)
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
                await _answer(query)
                return
        elif parts[1] == "new":
            await _remember_list(state, ["ls", "new", 0])
            reply = await _run(profile, actions.hr_new_page, profile, int(parts[2]))
        elif parts[1] == "ls":
            context = ["ls", parts[2], int(parts[3])]
            await _remember_list(state, context)
            reply = await _list_reply(profile, context, int(parts[4]))
        elif parts[1] in ("sr", "back"):
            reply = await _list_reply(profile, (await state.get_data()).get("hr_list"), int(parts[2]))
        elif parts[1] == "jobs":
            reply = await _run(profile, actions.hr_jobs_picker, profile, parts[2])
        elif parts[1] == "find":
            reply = await _run(profile, actions.hr_search_prompt, profile)
            if reply.awaiting_input:
                await state.set_state(Search.waiting)
                await query.message.answer(reply.text)
                await _answer(query)
                return
        elif parts[1] == "cv":
            reply = await _run(profile, actions.hr_resume, profile, int(parts[2]), int(parts[3]))
            # Keep the card; the file (or why there is none) comes below it.
            await _send(query, reply)
            return
        elif parts[1] == "fa":
            reply = await _run(profile, actions.hr_form_answers, profile, int(parts[2]), int(parts[3]))
        elif parts[1] == "aix":
            reply = await _run(profile, actions.hr_analysis_summary, profile, int(parts[2]), int(parts[3]))
        elif parts[1] in ("ai", "air"):
            reply = await _run(
                profile,
                partial(actions.hr_start_analysis, force=parts[1] == "air"),
                profile,
                int(parts[2]),
                int(parts[3]),
            )
        elif parts[1] in ("aiall", "aiallok"):
            reply = await _run(
                profile, partial(actions.hr_analyze_all, confirmed=parts[1] == "aiallok"), profile, int(parts[2])
            )
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
        await _answer(query)
        return
    await _show(query, reply)


async def _answer(query: CallbackQuery) -> None:
    """Stop the button's spinner; a query Telegram already expired is not an error."""
    try:
        await query.answer()
    except TelegramBadRequest:
        pass


async def _show(query: CallbackQuery, reply: "actions.Reply") -> None:
    try:
        await query.message.edit_text(
            reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True
        )
    except TelegramBadRequest as exc:
        # The same button pressed twice: the message already shows this.
        if "message is not modified" not in str(exc):
            # A message too old (or not editable): send the content anew.
            await query.message.answer(
                reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True
            )
    await _answer(query)


async def _send(query: CallbackQuery, reply: "actions.Reply") -> None:
    """Send a reply as a new message (a document when it carries one)."""
    if reply.document is not None:
        path, filename = reply.document
        try:
            await query.message.answer_document(FSInputFile(path, filename=filename), caption=reply.text)
        except Exception:  # noqa: BLE001 -- e.g. over Telegram's 50 MB limit, file gone
            logger.exception("Sending a resume file to Telegram failed")
            await query.message.answer(t(query.from_user.language_code, "resume_send_failed"))
    else:
        await query.message.answer(
            reply.text, reply_markup=_keyboard(reply.buttons), disable_web_page_preview=True
        )
    await _answer(query)


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


# Registered last: only what no handler above took reaches these.


@router.message()
async def on_unknown(message: Message) -> None:
    """An unknown command or a stray message gets a pointer to /help."""
    if message.from_user is None:
        return
    await message.answer(t(message.from_user.language_code, "unknown"))


@router.callback_query()
async def on_unknown_callback(query: CallbackQuery) -> None:
    """A button from an older bot version: just stop its spinner."""
    await _answer(query)
