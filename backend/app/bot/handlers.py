"""aiogram handlers: private-chat commands mapped onto ``app.bot.actions``."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from app.bot import actions
from app.bot.texts import t
from app.services.telegram.linking import TelegramProfile

logger = logging.getLogger(__name__)

router = Router(name="linking")
# Account data is personal: the bot only answers in one-to-one chats.
router.message.filter(F.chat.type == "private")


def _profile(message: Message) -> TelegramProfile:
    user = message.from_user
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
