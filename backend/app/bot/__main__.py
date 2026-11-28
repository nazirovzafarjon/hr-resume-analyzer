"""Start the Telegram bot: ``python -m app.bot``.

* ``TELEGRAM_WEBHOOK_URL`` empty: long polling (local development).
* ``TELEGRAM_WEBHOOK_URL`` set: Telegram pushes updates to that public HTTPS
  URL; the reverse proxy forwards its path to this process on
  ``TELEGRAM_WEBHOOK_PORT``. Every update must carry
  ``TELEGRAM_WEBHOOK_SECRET`` in the ``X-Telegram-Bot-Api-Secret-Token``
  header, so nobody else can feed the bot fake updates.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from urllib.parse import urlparse

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
    BotCommand(command="applications", description="Applications / Arizalar"),
    BotCommand(command="new", description="New applications (HR) / Yangi arizalar"),
    BotCommand(command="jobs", description="Jobs (HR) / Vakansiyalar"),
    BotCommand(command="interviews", description="Interviews (HR) / Suhbatlar"),
    BotCommand(command="stats", description="Stats (HR) / Statistika"),
    BotCommand(command="settings", description="Notifications / Sozlamalar"),
    BotCommand(command="status", description="Connected accounts / Ulangan akkauntlar"),
    BotCommand(command="unlink", description="Disconnect / Uzish"),
    BotCommand(command="help", description="Help / Yordam"),
]

ALLOWED_UPDATES = ["message", "callback_query"]

#: What Telegram accepts as ``secret_token`` (1-256 of A-Z a-z 0-9 _ -).
_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def webhook_config_error() -> str | None:
    """Why the webhook settings cannot be used, or ``None`` when they are fine."""
    url = settings.TELEGRAM_WEBHOOK_URL.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return "TELEGRAM_WEBHOOK_URL must be a public https:// URL"
    if not _SECRET_RE.match(settings.TELEGRAM_WEBHOOK_SECRET):
        return "TELEGRAM_WEBHOOK_SECRET must be 1-256 characters of A-Z, a-z, 0-9, _ or -"
    return None


def webhook_path() -> str:
    return urlparse(settings.TELEGRAM_WEBHOOK_URL.strip()).path or "/"


def _build() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return bot, dispatcher


async def run_polling() -> None:
    bot, dispatcher = _build()
    await bot.set_my_commands(COMMANDS)
    # Polling and a webhook cannot both be active; clear any leftover webhook.
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Telegram bot @%s started (polling)", settings.TELEGRAM_BOT_USERNAME)
    try:
        await dispatcher.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        await bot.session.close()


async def run_webhook() -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot, dispatcher = _build()
    secret = settings.TELEGRAM_WEBHOOK_SECRET

    async def on_startup(**_: object) -> None:
        await bot.set_my_commands(COMMANDS)
        await bot.set_webhook(
            settings.TELEGRAM_WEBHOOK_URL.strip(),
            secret_token=secret,
            allowed_updates=ALLOWED_UPDATES,
        )

    dispatcher.startup.register(on_startup)
    app = web.Application()
    # Rejects requests without the right secret header (403).
    SimpleRequestHandler(dispatcher=dispatcher, bot=bot, secret_token=secret).register(
        app, path=webhook_path()
    )
    setup_application(app, dispatcher, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.TELEGRAM_WEBHOOK_PORT)
    await site.start()
    logger.info(
        "Telegram bot @%s started (webhook on :%s%s)",
        settings.TELEGRAM_BOT_USERNAME,
        settings.TELEGRAM_WEBHOOK_PORT,
        webhook_path(),
    )
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    configure_logging(service_name="resume-analyzer-bot")
    if not settings.telegram_configured:
        logger.error(
            "Telegram bot is disabled: set TELEGRAM_ENABLED=true, TELEGRAM_BOT_TOKEN "
            "and TELEGRAM_BOT_USERNAME."
        )
        sys.exit(1)
    problem = webhook_config_error()
    if problem:
        logger.error("Telegram webhook is misconfigured: %s", problem)
        sys.exit(1)
    asyncio.run(run_webhook() if settings.TELEGRAM_WEBHOOK_URL.strip() else run_polling())
