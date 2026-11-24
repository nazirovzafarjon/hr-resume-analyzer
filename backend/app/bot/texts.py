"""Bot replies in the three interface languages (uz, ru, en).

Texts are HTML (the bot sends with ``parse_mode=HTML``); anything inserted
into them must be escaped by the caller.
"""

from app.services.telegram.linking import normalize_language

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "welcome": (
            "👋 Assalomu alaykum! Bu <b>Resume Analyzer</b> boti.\n\n"
            "Bot orqali arizalar va ularning holati haqida xabar olasiz. "
            "Ulash uchun saytga kiring va <b>Sozlamalar → Telegram</b> (HR) yoki "
            "<b>Profil → Telegram</b> (nomzod) bo'limidagi «Telegramni ulash» tugmasini bosing.\n\n"
            "{site}"
        ),
        "linked_hr": "✅ Telegram HR akkauntingizga ulandi: <b>{email}</b>.\nYangi arizalar haqida shu yerga xabar keladi.",
        "linked_candidate": "✅ Telegram nomzod akkauntingizga ulandi: <b>{email}</b>.\nArizalaringiz holati o'zgarganda shu yerga xabar keladi.",
        "token_invalid": "⚠️ Havola noto'g'ri yoki allaqachon ishlatilgan. Saytdan yangi havola oling.",
        "token_expired": "⌛ Havolaning muddati tugagan. Saytdan yangi havola oling.",
        "token_inactive": "⛔ Akkaunt faol emas yoki emaili tasdiqlanmagan.",
        "status_header": "🔗 Ulangan akkauntlar:",
        "status_hr": "• HR: <b>{email}</b>",
        "status_candidate": "• Nomzod: <b>{email}</b>",
        "status_none": "Hali hech qanday akkaunt ulanmagan. /start ni bosing.",
        "unlinked": "🔌 Telegram akkauntlardan uzildi. Endi xabar kelmaydi.",
        "unlink_none": "Uziladigan akkaunt yo'q.",
        "help": (
            "Komandalar:\n"
            "/start — boshlash\n"
            "/status — ulangan akkauntlar\n"
            "/unlink — Telegramni akkauntlardan uzish\n"
            "/help — yordam"
        ),
        "error": "Xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.",
    },
    "ru": {
        "welcome": (
            "👋 Здравствуйте! Это бот <b>Resume Analyzer</b>.\n\n"
            "Здесь вы будете получать уведомления о заявках и их статусе. "
            "Чтобы подключить аккаунт, откройте сайт и нажмите «Подключить Telegram» в разделе "
            "<b>Настройки → Telegram</b> (HR) или <b>Профиль → Telegram</b> (кандидат).\n\n"
            "{site}"
        ),
        "linked_hr": "✅ Telegram подключён к HR-аккаунту <b>{email}</b>.\nСюда будут приходить новые заявки.",
        "linked_candidate": "✅ Telegram подключён к аккаунту кандидата <b>{email}</b>.\nСюда будут приходить изменения статуса ваших заявок.",
        "token_invalid": "⚠️ Ссылка недействительна или уже использована. Получите новую на сайте.",
        "token_expired": "⌛ Срок действия ссылки истёк. Получите новую на сайте.",
        "token_inactive": "⛔ Аккаунт неактивен или email не подтверждён.",
        "status_header": "🔗 Подключённые аккаунты:",
        "status_hr": "• HR: <b>{email}</b>",
        "status_candidate": "• Кандидат: <b>{email}</b>",
        "status_none": "Аккаунты ещё не подключены. Нажмите /start.",
        "unlinked": "🔌 Telegram отключён от аккаунтов. Уведомления больше не придут.",
        "unlink_none": "Нет подключённых аккаунтов.",
        "help": (
            "Команды:\n"
            "/start — начать\n"
            "/status — подключённые аккаунты\n"
            "/unlink — отключить Telegram от аккаунтов\n"
            "/help — помощь"
        ),
        "error": "Произошла ошибка. Попробуйте ещё раз чуть позже.",
    },
    "en": {
        "welcome": (
            "👋 Hello! This is the <b>Resume Analyzer</b> bot.\n\n"
            "You will get notifications about applications and their status here. "
            "To connect your account, open the website and press “Connect Telegram” in "
            "<b>Settings → Telegram</b> (HR) or <b>Profile → Telegram</b> (candidate).\n\n"
            "{site}"
        ),
        "linked_hr": "✅ Telegram is connected to the HR account <b>{email}</b>.\nNew applications will be sent here.",
        "linked_candidate": "✅ Telegram is connected to the candidate account <b>{email}</b>.\nStatus changes of your applications will be sent here.",
        "token_invalid": "⚠️ This link is invalid or was already used. Get a new one on the website.",
        "token_expired": "⌛ This link has expired. Get a new one on the website.",
        "token_inactive": "⛔ The account is inactive or its email is not verified.",
        "status_header": "🔗 Connected accounts:",
        "status_hr": "• HR: <b>{email}</b>",
        "status_candidate": "• Candidate: <b>{email}</b>",
        "status_none": "No account is connected yet. Press /start.",
        "unlinked": "🔌 Telegram was disconnected from your accounts. No more notifications.",
        "unlink_none": "There is no connected account.",
        "help": (
            "Commands:\n"
            "/start — start\n"
            "/status — connected accounts\n"
            "/unlink — disconnect Telegram from your accounts\n"
            "/help — help"
        ),
        "error": "Something went wrong. Please try again a bit later.",
    },
}


def t(language_code: str | None, key: str, **params: str) -> str:
    """Text ``key`` in the user's language, with ``params`` filled in."""
    return TEXTS[normalize_language(language_code)][key].format(**params)
