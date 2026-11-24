"""aiogram handlers: private-chat commands mapped onto ``app.bot.actions``."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
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
