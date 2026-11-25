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
            "/applications — arizalarim va ularning holati\n"
            "/new — ko'rib chiqilmagan arizalar (HR)\n"
            "/status — ulangan akkauntlar\n"
            "/unlink — Telegramni akkauntlardan uzish\n"
            "/help — yordam"
        ),
        "status_changed": "📌 <b>Ariza holati yangilandi</b>\n\n<b>{position}</b> — {company}\n{emoji} {status}",
        "application_received": "📨 <b>Arizangiz qabul qilindi</b>\n\n<b>{position}</b> — {company}\nHolat o'zgarganda shu yerga xabar beraman.",
        "btn_details": "🔎 Batafsil",
        "btn_open_site": "🌐 Saytda ochish",
        "btn_back": "‹ Ro'yxatga",
        "btn_prev": "‹ Oldingi",
        "btn_next": "Keyingi ›",
        "apps_header": "📋 <b>Arizalaringiz</b> ({total} ta) — {page}/{pages}",
        "apps_empty": "Hali ariza topshirmagansiz. Saytda vakansiyaga ariza berishda akkauntingizga kirgan bo'ling — shunda ariza shu yerda ko'rinadi.",
        "apps_not_candidate": "Bu komanda nomzodlar uchun. Saytda <b>Profil → Telegram</b> bo'limidan nomzod akkauntingizni ulang.",
        "app_not_found": "Ariza topilmadi.",
        "app_submitted": "Yuborilgan: {date}",
        "app_next_interview": "🗓 Suhbat: <b>{date}</b>",
        "app_timeline": "<b>Jarayon:</b>",
        "new_application": "🆕 <b>Yangi ariza</b>\n\n<b>{position}</b> — {company}\n👤 {name}\n🕒 {date}",
        "btn_open_crm": "🌐 CRM'da ochish",
        "hr_new_header": "🆕 <b>Ko'rib chiqilmagan arizalar</b> ({total} ta) — {page}/{pages}",
        "hr_new_empty": "Ko'rib chiqilmagan ariza yo'q. 🎉",
        "hr_not_hr": "Bu komanda HR uchun. Saytda <b>Sozlamalar → Telegram</b> bo'limidan HR akkauntingizni ulang.",
        "hr_app_status": "Holat: <b>{status}</b>",
        "hr_ai_score": "🤖 AI moslik: <b>{score}%</b>",
        "hr_ai_none": "🤖 AI tahlili hali o'tkazilmagan",
        "hr_ai_running": "🤖 AI tahlili davom etmoqda",
        "hr_ai_failed": "🤖 AI tahlili amalga oshmadi",
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
            "/applications — мои заявки и их статус\n"
            "/new — нерассмотренные заявки (HR)\n"
            "/status — подключённые аккаунты\n"
            "/unlink — отключить Telegram от аккаунтов\n"
            "/help — помощь"
        ),
        "status_changed": "📌 <b>Статус заявки обновлён</b>\n\n<b>{position}</b> — {company}\n{emoji} {status}",
        "application_received": "📨 <b>Ваша заявка получена</b>\n\n<b>{position}</b> — {company}\nЯ сообщу сюда, когда статус изменится.",
        "btn_details": "🔎 Подробнее",
        "btn_open_site": "🌐 Открыть на сайте",
        "btn_back": "‹ К списку",
        "btn_prev": "‹ Назад",
        "btn_next": "Далее ›",
        "apps_header": "📋 <b>Ваши заявки</b> ({total}) — {page}/{pages}",
        "apps_empty": "У вас пока нет заявок. Откликайтесь на вакансии на сайте, войдя в аккаунт, — тогда заявки появятся здесь.",
        "apps_not_candidate": "Эта команда для кандидатов. Подключите аккаунт кандидата в разделе <b>Профиль → Telegram</b> на сайте.",
        "app_not_found": "Заявка не найдена.",
        "app_submitted": "Отправлена: {date}",
        "app_next_interview": "🗓 Собеседование: <b>{date}</b>",
        "app_timeline": "<b>Этапы:</b>",
        "new_application": "🆕 <b>Новая заявка</b>\n\n<b>{position}</b> — {company}\n👤 {name}\n🕒 {date}",
        "btn_open_crm": "🌐 Открыть в CRM",
        "hr_new_header": "🆕 <b>Нерассмотренные заявки</b> ({total}) — {page}/{pages}",
        "hr_new_empty": "Нерассмотренных заявок нет. 🎉",
        "hr_not_hr": "Эта команда для HR. Подключите HR-аккаунт в разделе <b>Настройки → Telegram</b> на сайте.",
        "hr_app_status": "Статус: <b>{status}</b>",
        "hr_ai_score": "🤖 Соответствие (ИИ): <b>{score}%</b>",
        "hr_ai_none": "🤖 Анализ ИИ ещё не проводился",
        "hr_ai_running": "🤖 Идёт анализ ИИ",
        "hr_ai_failed": "🤖 Анализ ИИ не удался",
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
            "/applications — my applications and their status\n"
            "/new — unreviewed applications (HR)\n"
            "/status — connected accounts\n"
            "/unlink — disconnect Telegram from your accounts\n"
            "/help — help"
        ),
        "status_changed": "📌 <b>Application status updated</b>\n\n<b>{position}</b> — {company}\n{emoji} {status}",
        "application_received": "📨 <b>Your application was received</b>\n\n<b>{position}</b> — {company}\nI'll message you here when its status changes.",
        "btn_details": "🔎 Details",
        "btn_open_site": "🌐 Open on the website",
        "btn_back": "‹ Back to list",
        "btn_prev": "‹ Previous",
        "btn_next": "Next ›",
        "apps_header": "📋 <b>Your applications</b> ({total}) — {page}/{pages}",
        "apps_empty": "You have no applications yet. Apply on the website while signed in to your account and they will show up here.",
        "apps_not_candidate": "This command is for candidates. Connect your candidate account in <b>Profile → Telegram</b> on the website.",
        "app_not_found": "Application not found.",
        "app_submitted": "Submitted: {date}",
        "app_next_interview": "🗓 Interview: <b>{date}</b>",
        "app_timeline": "<b>Progress:</b>",
        "new_application": "🆕 <b>New application</b>\n\n<b>{position}</b> — {company}\n👤 {name}\n🕒 {date}",
        "btn_open_crm": "🌐 Open in CRM",
        "hr_new_header": "🆕 <b>Unreviewed applications</b> ({total}) — {page}/{pages}",
        "hr_new_empty": "No unreviewed applications. 🎉",
        "hr_not_hr": "This command is for HR. Connect your HR account in <b>Settings → Telegram</b> on the website.",
        "hr_app_status": "Status: <b>{status}</b>",
        "hr_ai_score": "🤖 AI match: <b>{score}%</b>",
        "hr_ai_none": "🤖 No AI analysis yet",
        "hr_ai_running": "🤖 AI analysis in progress",
        "hr_ai_failed": "🤖 AI analysis failed",
        "error": "Something went wrong. Please try again a bit later.",
    },
}


def t(language_code: str | None, key: str, **params: str) -> str:
    """Text ``key`` in the user's language, with ``params`` filled in."""
    return TEXTS[normalize_language(language_code)][key].format(**params)


#: Candidate-facing status labels, worded exactly like the Candidate Portal.
STATUS_LABELS: dict[str, dict[str, str]] = {
    "uz": {
        "submitted": "Ariza yuborildi",
        "ai_review": "Rezyume tahlil qilinmoqda",
        "hr_review": "HR ko'rib chiqmoqda",
        "interview_invited": "Suhbatga taklif",
        "interview_scheduled": "Suhbat belgilandi",
        "decision_pending": "Qaror kutilmoqda",
        "accepted": "Ariza qabul qilindi",
        "rejected": "Ariza yopildi",
        "withdrawn": "Ariza qaytarib olindi",
    },
    "ru": {
        "submitted": "Заявка отправлена",
        "ai_review": "Резюме анализируется",
        "hr_review": "На рассмотрении HR",
        "interview_invited": "Приглашение на собеседование",
        "interview_scheduled": "Собеседование назначено",
        "decision_pending": "Ожидается решение",
        "accepted": "Заявка принята",
        "rejected": "Заявка закрыта",
        "withdrawn": "Заявка отозвана",
    },
    "en": {
        "submitted": "Application submitted",
        "ai_review": "Resume being reviewed",
        "hr_review": "Under HR review",
        "interview_invited": "Interview invitation",
        "interview_scheduled": "Interview scheduled",
        "decision_pending": "Decision pending",
        "accepted": "Application accepted",
        "rejected": "Application closed",
        "withdrawn": "Application withdrawn",
    },
}

STATUS_EMOJI: dict[str, str] = {
    "submitted": "📨",
    "ai_review": "🔍",
    "hr_review": "👀",
    "interview_invited": "📅",
    "interview_scheduled": "🗓",
    "decision_pending": "⏳",
    "accepted": "🎉",
    "rejected": "📁",
    "withdrawn": "↩️",
}

#: Timeline step names (``services.candidate_portal.timeline`` keys).
TIMELINE_LABELS: dict[str, dict[str, str]] = {
    "uz": {
        "submitted": "Ariza yuborildi",
        "resume_review": "Rezyume tahlili",
        "hr_review": "HR ko'rib chiqishi",
        "interview": "Suhbat",
        "decision": "Yakuniy qaror",
        "decision_accepted": "Ariza qabul qilindi",
        "decision_rejected": "Ariza yopildi",
        "decision_withdrawn": "Ariza qaytarib olindi",
    },
    "ru": {
        "submitted": "Заявка отправлена",
        "resume_review": "Анализ резюме",
        "hr_review": "Рассмотрение HR",
        "interview": "Собеседование",
        "decision": "Итоговое решение",
        "decision_accepted": "Заявка принята",
        "decision_rejected": "Заявка закрыта",
        "decision_withdrawn": "Заявка отозвана",
    },
    "en": {
        "submitted": "Application submitted",
        "resume_review": "Resume review",
        "hr_review": "HR review",
        "interview": "Interview",
        "decision": "Final decision",
        "decision_accepted": "Application accepted",
        "decision_rejected": "Application closed",
        "decision_withdrawn": "Application withdrawn",
    },
}

TIMELINE_STATE_EMOJI: dict[str, str] = {
    "done": "✅",
    "current": "🔄",
    "upcoming": "⚪",
    "skipped": "➖",
    "unavailable": "⚠️",
}


def status_label(language_code: str | None, status: str) -> str:
    return STATUS_LABELS[normalize_language(language_code)][status]


def timeline_label(language_code: str | None, key: str) -> str:
    return TIMELINE_LABELS[normalize_language(language_code)][key]


#: HR pipeline status labels, worded exactly like the CRM.
HR_STATUS_LABELS: dict[str, dict[str, str]] = {
    "uz": {
        "new": "Yangi",
        "reviewing": "Ko'rib chiqilmoqda",
        "shortlisted": "Tanlangan",
        "interview": "Suhbat",
        "hired": "Ishga olindi",
        "rejected": "Rad etilgan",
        "withdrawn": "Qaytarib olingan",
    },
    "ru": {
        "new": "Новая",
        "reviewing": "На проверке",
        "shortlisted": "В отборе",
        "interview": "Собеседование",
        "hired": "Принят",
        "rejected": "Отклонена",
        "withdrawn": "Отозвана",
    },
    "en": {
        "new": "New",
        "reviewing": "Reviewing",
        "shortlisted": "Shortlisted",
        "interview": "Interview",
        "hired": "Hired",
        "rejected": "Rejected",
        "withdrawn": "Withdrawn",
    },
}


def hr_status_label(language_code: str | None, status: str) -> str:
    return HR_STATUS_LABELS[normalize_language(language_code)][status]
