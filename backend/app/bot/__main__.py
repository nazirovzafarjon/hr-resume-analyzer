"""Start the Telegram bot with long polling: ``python -m app.bot``."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.bot.handlers import router
from app.core.config import settings
from app.core.logging_config import configure_logging

logger = logging.getLogger("app.bot")

COMMANDS = [
    BotCommand(command="start", description="Start / Boshlash"),
    BotCommand(command="status", description="Connected accounts / Ulangan akkauntlar"),
    BotCommand(command="unlink", description="Disconnect / Uzish"),
    BotCommand(command="help", description="Help / Yordam"),
]


async def main() -> None:
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await bot.set_my_commands(COMMANDS)
    # Polling and a webhook cannot both be active; clear any leftover webhook.
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Telegram bot @%s started (polling)", settings.TELEGRAM_BOT_USERNAME)
    try:
        await dispatcher.start_polling(bot, allowed_updates=["message"])
    finally:
        await bot.session.close()


if __name__ == "__main__":
    configure_logging(service_name="resume-analyzer-bot")
    if not settings.telegram_configured:
        logger.error(
            "Telegram bot is disabled: set TELEGRAM_ENABLED=true, TELEGRAM_BOT_TOKEN "
            "and TELEGRAM_BOT_USERNAME."
        )
        sys.exit(1)
    asyncio.run(main())
