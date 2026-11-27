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
            "/settings — xabarnoma sozlamalari\n"
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
        "hr_confirm": "👤 <b>{name}</b> — {position}\n\nHolat «<b>{status}</b>» ga o'zgartirilsinmi? Bu yakuniy qaror; nomzod Telegram'ga ulangan bo'lsa, unga xabar boradi.",
        "hr_status_set": "✅ Holat o'zgartirildi: <b>{status}</b>",
        "btn_confirm": "✅ Ha, tasdiqlayman",
        "btn_cancel": "‹ Bekor qilish",
        "reminder_title": "⏰ <b>Suhbat eslatmasi</b>",
        "reminder_day": "Suhbatga 24 soatdan kam vaqt qoldi.",
        "reminder_hour": "Suhbat 1 soatdan keyin boshlanadi.",
        "settings_header": "⚙️ <b>Xabarnoma sozlamalari</b>\nTugmani bosib yoqing yoki o'chiring.",
        "settings_none": "Sozlash uchun avval akkauntingizni ulang. /start ni bosing.",
        "settings_hr": "<b>HR</b>",
        "settings_candidate": "<b>Nomzod</b>",
        "pref_status": "Ariza holati o'zgarishi",
        "pref_new_applications": "Yangi arizalar",
        "pref_reminders": "Suhbat eslatmalari",
        "btn_schedule": "🗓 Suhbat belgilash",
        "iv_heading": "🗓 <b>Suhbat belgilash</b>\n👤 {name} — {position}",
        "iv_pick_day": "Kunni tanlang (vaqt: {tz}):",
        "iv_pick_time": "<b>{day}</b> — boshlanish vaqtini tanlang:",
        "iv_duration": "⏱ Davomiyligi: {minutes} daqiqa",
        "iv_minutes": "{minutes} daq",
        "iv_interviewer": "🎙 Suhbatdosh: {name}",
        "iv_review_hint": "Davomiylikni tanlang va tasdiqlang.",
        "btn_iv_confirm": "✅ Suhbatni belgilash",
        "btn_back_step": "‹ Orqaga",
        "btn_to_card": "‹ Arizaga",
        "iv_scheduled": "✅ <b>Suhbat belgilandi</b>",
        "iv_reminders_hint": "Telegram ulangan bo'lsa, suhbatdan 24 soat va 1 soat oldin sizga va nomzodga eslatma boradi.",
        "iv_closed": "Bu ariza yopilgan — suhbat belgilab bo'lmaydi.",
        "iv_slot_gone": "⌛ Bu vaqt endi mavjud emas. Boshqasini tanlang.",
        "btn_add_link": "🔗 Uchrashuv havolasini qo'shish",
        "btn_change_link": "🔗 Havolani o'zgartirish",
        "iv_link_prompt": "🔗 Uchrashuv havolasini yuboring (Zoom, Google Meet, https://…).\nBekor qilish: /cancel",
        "iv_link_invalid": "⚠️ Bu havolaga o'xshamaydi. https:// bilan boshlanadigan havola yuboring yoki /cancel.",
        "iv_link_saved": "✅ <b>Havola saqlandi</b>",
        "iv_not_found": "Suhbat topilmadi yoki u allaqachon o'tgan.",
        "pref_interviews": "Suhbatlar: o'zgarishlar va eslatmalar",
        "iv_update_scheduled": "🗓 <b>Siz suhbatga taklif qilindingiz</b>",
        "iv_update_rescheduled": "🔁 <b>Suhbat vaqti o'zgardi</b>",
        "iv_update_cancelled": "❌ <b>Suhbat bekor qilindi</b>",
        "iv_update_link": "🔗 <b>Suhbat havolasi qo'shildi</b>",
        "iv_update_previous": "Avvalgi vaqt: <s>{date}</s>",
        "btn_reschedule": "🔁 Vaqtini o'zgartirish",
        "btn_iv_cancel": "❌ Suhbatni bekor qilish",
        "iv_reschedule_heading": "🔁 <b>Suhbat vaqtini o'zgartirish</b>\n👤 {name} — {position}\nHozirgi vaqt: {date}",
        "btn_iv_reschedule_confirm": "✅ Yangi vaqtni saqlash",
        "iv_rescheduled": "✅ <b>Suhbat vaqti o'zgartirildi</b>",
        "iv_cancel_confirm": "Suhbatni bekor qilasizmi?\n\n👤 <b>{name}</b> — {position}\n🗓 {date}\n\nNomzod Telegram ulagan bo'lsa, unga xabar boradi.",
        "btn_iv_cancel_confirm": "❌ Ha, bekor qilish",
        "btn_keep": "‹ Yo'q, qoldirish",
        "iv_cancelled": "❌ Suhbat bekor qilindi.",
        "iv_change_hint": "Nomzod Telegram ulagan bo'lsa, o'zgarish haqida unga xabar boradi.",
        "cancelled": "Bekor qilindi.",
        "nothing_to_cancel": "Bekor qiladigan narsa yo'q.",
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
            "/settings — настройки уведомлений\n"
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
        "hr_confirm": "👤 <b>{name}</b> — {position}\n\nИзменить статус на «<b>{status}</b>»? Это итоговое решение; если кандидат подключил Telegram, он получит уведомление.",
        "hr_status_set": "✅ Статус изменён: <b>{status}</b>",
        "btn_confirm": "✅ Да, подтверждаю",
        "btn_cancel": "‹ Отмена",
        "reminder_title": "⏰ <b>Напоминание о собеседовании</b>",
        "reminder_day": "До собеседования меньше 24 часов.",
        "reminder_hour": "Собеседование начнётся через час.",
        "settings_header": "⚙️ <b>Настройки уведомлений</b>\nНажмите, чтобы включить или выключить.",
        "settings_none": "Сначала подключите аккаунт. Нажмите /start.",
        "settings_hr": "<b>HR</b>",
        "settings_candidate": "<b>Кандидат</b>",
        "pref_status": "Изменения статуса заявки",
        "pref_new_applications": "Новые заявки",
        "pref_reminders": "Напоминания о собеседованиях",
        "btn_schedule": "🗓 Назначить собеседование",
        "iv_heading": "🗓 <b>Назначение собеседования</b>\n👤 {name} — {position}",
        "iv_pick_day": "Выберите день (время: {tz}):",
        "iv_pick_time": "<b>{day}</b> — выберите время начала:",
        "iv_duration": "⏱ Длительность: {minutes} мин",
        "iv_minutes": "{minutes} мин",
        "iv_interviewer": "🎙 Интервьюер: {name}",
        "iv_review_hint": "Выберите длительность и подтвердите.",
        "btn_iv_confirm": "✅ Назначить собеседование",
        "btn_back_step": "‹ Назад",
        "btn_to_card": "‹ К заявке",
        "iv_scheduled": "✅ <b>Собеседование назначено</b>",
        "iv_reminders_hint": "Если Telegram подключён, вы и кандидат получите напоминания за 24 часа и за 1 час.",
        "iv_closed": "Заявка закрыта — назначить собеседование нельзя.",
        "iv_slot_gone": "⌛ Это время уже недоступно. Выберите другое.",
        "btn_add_link": "🔗 Добавить ссылку на встречу",
        "btn_change_link": "🔗 Изменить ссылку",
        "iv_link_prompt": "🔗 Отправьте ссылку на встречу (Zoom, Google Meet, https://…).\nОтмена: /cancel",
        "iv_link_invalid": "⚠️ Это не похоже на ссылку. Отправьте ссылку, начинающуюся с https://, или /cancel.",
        "iv_link_saved": "✅ <b>Ссылка сохранена</b>",
        "iv_not_found": "Собеседование не найдено или уже прошло.",
        "pref_interviews": "Собеседования: изменения и напоминания",
        "iv_update_scheduled": "🗓 <b>Вас пригласили на собеседование</b>",
        "iv_update_rescheduled": "🔁 <b>Время собеседования изменилось</b>",
        "iv_update_cancelled": "❌ <b>Собеседование отменено</b>",
        "iv_update_link": "🔗 <b>Добавлена ссылка на собеседование</b>",
        "iv_update_previous": "Прежнее время: <s>{date}</s>",
        "btn_reschedule": "🔁 Перенести",
        "btn_iv_cancel": "❌ Отменить собеседование",
        "iv_reschedule_heading": "🔁 <b>Перенос собеседования</b>\n👤 {name} — {position}\nСейчас: {date}",
        "btn_iv_reschedule_confirm": "✅ Сохранить новое время",
        "iv_rescheduled": "✅ <b>Собеседование перенесено</b>",
        "iv_cancel_confirm": "Отменить собеседование?\n\n👤 <b>{name}</b> — {position}\n🗓 {date}\n\nЕсли кандидат подключил Telegram, он получит уведомление.",
        "btn_iv_cancel_confirm": "❌ Да, отменить",
        "btn_keep": "‹ Нет, оставить",
        "iv_cancelled": "❌ Собеседование отменено.",
        "iv_change_hint": "Если кандидат подключил Telegram, он получит уведомление об изменении.",
        "cancelled": "Отменено.",
        "nothing_to_cancel": "Нечего отменять.",
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
            "/settings — notification settings\n"
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
        "hr_confirm": "👤 <b>{name}</b> — {position}\n\nChange the status to “<b>{status}</b>”? This is a final decision; if the candidate connected Telegram, they will be notified.",
        "hr_status_set": "✅ Status changed: <b>{status}</b>",
        "btn_confirm": "✅ Yes, confirm",
        "btn_cancel": "‹ Cancel",
        "reminder_title": "⏰ <b>Interview reminder</b>",
        "reminder_day": "The interview is less than 24 hours away.",
        "reminder_hour": "The interview starts in an hour.",
        "settings_header": "⚙️ <b>Notification settings</b>\nTap a button to turn it on or off.",
        "settings_none": "Connect your account first. Tap /start.",
        "settings_hr": "<b>HR</b>",
        "settings_candidate": "<b>Candidate</b>",
        "pref_status": "Application status changes",
        "pref_new_applications": "New applications",
        "pref_reminders": "Interview reminders",
        "btn_schedule": "🗓 Schedule interview",
        "iv_heading": "🗓 <b>Schedule an interview</b>\n👤 {name} — {position}",
        "iv_pick_day": "Pick a day (time zone: {tz}):",
        "iv_pick_time": "<b>{day}</b> — pick a start time:",
        "iv_duration": "⏱ Duration: {minutes} min",
        "iv_minutes": "{minutes} min",
        "iv_interviewer": "🎙 Interviewer: {name}",
        "iv_review_hint": "Choose the duration and confirm.",
        "btn_iv_confirm": "✅ Schedule interview",
        "btn_back_step": "‹ Back",
        "btn_to_card": "‹ To the application",
        "iv_scheduled": "✅ <b>Interview scheduled</b>",
        "iv_reminders_hint": "If Telegram is connected, you and the candidate get reminders 24 hours and 1 hour before.",
        "iv_closed": "This application is closed — an interview cannot be scheduled.",
        "iv_slot_gone": "⌛ That time is no longer available. Pick another one.",
        "btn_add_link": "🔗 Add meeting link",
        "btn_change_link": "🔗 Change the link",
        "iv_link_prompt": "🔗 Send the meeting link (Zoom, Google Meet, https://…).\nCancel: /cancel",
        "iv_link_invalid": "⚠️ That doesn't look like a link. Send one starting with https://, or /cancel.",
        "iv_link_saved": "✅ <b>Link saved</b>",
        "iv_not_found": "Interview not found, or it is already over.",
        "pref_interviews": "Interviews: changes and reminders",
        "iv_update_scheduled": "🗓 <b>You are invited to an interview</b>",
        "iv_update_rescheduled": "🔁 <b>Your interview was moved</b>",
        "iv_update_cancelled": "❌ <b>Your interview was cancelled</b>",
        "iv_update_link": "🔗 <b>Meeting link added to your interview</b>",
        "iv_update_previous": "Previously: <s>{date}</s>",
        "btn_reschedule": "🔁 Reschedule",
        "btn_iv_cancel": "❌ Cancel interview",
        "iv_reschedule_heading": "🔁 <b>Reschedule the interview</b>\n👤 {name} — {position}\nCurrently: {date}",
        "btn_iv_reschedule_confirm": "✅ Save the new time",
        "iv_rescheduled": "✅ <b>Interview rescheduled</b>",
        "iv_cancel_confirm": "Cancel this interview?\n\n👤 <b>{name}</b> — {position}\n🗓 {date}\n\nIf the candidate connected Telegram, they will be told.",
        "btn_iv_cancel_confirm": "❌ Yes, cancel it",
        "btn_keep": "‹ No, keep it",
        "iv_cancelled": "❌ Interview cancelled.",
        "iv_change_hint": "If the candidate connected Telegram, they will be told about the change.",
        "cancelled": "Cancelled.",
        "nothing_to_cancel": "Nothing to cancel.",
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


#: Buttons on the HR card that move an application (phase 4).
HR_ACTION_LABELS: dict[str, dict[str, str]] = {
    "uz": {
        "reviewing": "👀 Ko'rib chiqishni boshlash",
        "shortlisted": "⭐ Tanlash",
        "interview": "📅 Suhbatga",
        "hired": "🎉 Ishga olish",
        "rejected": "❌ Rad etish",
    },
    "ru": {
        "reviewing": "👀 Начать проверку",
        "shortlisted": "⭐ В отбор",
        "interview": "📅 На собеседование",
        "hired": "🎉 Принять",
        "rejected": "❌ Отклонить",
    },
    "en": {
        "reviewing": "👀 Start review",
        "shortlisted": "⭐ Shortlist",
        "interview": "📅 Interview",
        "hired": "🎉 Hire",
        "rejected": "❌ Reject",
    },
}


def hr_action_label(language_code: str | None, status: str) -> str:
    return HR_ACTION_LABELS[normalize_language(language_code)][status]


#: Short weekday names, Monday first (``date.weekday()``), for the day picker.
WEEKDAYS: dict[str, tuple[str, ...]] = {
    "uz": ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}


def weekday_label(language_code: str | None, weekday: int) -> str:
    return WEEKDAYS[normalize_language(language_code)][weekday]
