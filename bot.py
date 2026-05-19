import asyncio
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config as cfg
import webook_api as wk
from database import (
    init_db,
    add_user,
    subscribe,
    unsubscribe,
    get_user_subscriptions,
    get_event_subscribers,
    save_booking_request,
    get_prefs,
    set_pref,
    save_webook_token,
    get_webook_token,
    mark_event_seen,
    is_event_seen,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

EMAIL, PHONE = range(1, 3)


_seen_event_slugs = set()

ADMIN_CHAT_ID = cfg.ADMIN_CHAT_ID
BOT_TOKEN = cfg.BOT_TOKEN
CHECK_INTERVAL = cfg.CHECK_INTERVAL


async def start(update: Update, context):
    user = update.effective_user
    add_user(user.id, user.first_name, user.username)

    global ADMIN_CHAT_ID
    if ADMIN_CHAT_ID is None:
        ADMIN_CHAT_ID = user.id
        logger.info(f"Admin auto-set to user_id: {user.id}")

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context, edit=False):
    uid = update.effective_user.id
    webook_token = get_webook_token(uid)
    logged_in = webook_token is not None and bool(webook_token.get("access_token"))

    keyboard = [
        [InlineKeyboardButton("📅 الفعاليات المتاحة", callback_data="events")],
        [InlineKeyboardButton("🏟️ الفرق الرياضية", callback_data="teams")],
        [InlineKeyboardButton("🔔 إشعاراتي", callback_data="my_notifications")],
    ]
    if logged_in:
        keyboard.append([InlineKeyboardButton("🎫 حجز تذكرة WeBook", callback_data="webook_booking")])
    else:
        keyboard.append([InlineKeyboardButton("🎫 إرسال بيانات الحجز", callback_data="webook_login")])
    keyboard.append([InlineKeyboardButton("📋 بياناتي", callback_data="my_data")])
    keyboard.append([InlineKeyboardButton("🔧 الدعم الفني", callback_data="support")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"مرحباً {update.effective_user.first_name}! 👋\n🎟️ بوت WeBook - اختر من القائمة:"
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "events":
        await show_events(update, context)
    elif data.startswith("org_"):
        org_slug = data[4:]
        await show_org_events(update, context, org_slug)
    elif data.startswith("event_"):
        event_slug = data[6:]
        await show_event_detail(update, context, event_slug)
    elif data == "teams":
        await show_teams(update, context)
    elif data.startswith("team_events_"):
        team_id = data[12:]
        await show_team_events(update, context, team_id)
    elif data == "my_notifications":
        await show_my_notifications(update, context)
    elif data.startswith("sub_"):
        event_slug = data[4:]
        event_title = context.user_data.get(f"title_{event_slug}", event_slug)
        subscribe(update.effective_user.id, event_slug, event_title)
        await query.answer(f"✅ تم تفعيل الإشعارات")
        await show_my_notifications(update, context)
    elif data.startswith("unsub_"):
        event_slug = data[5:]
        unsubscribe(update.effective_user.id, event_slug)
        await query.answer(f"❌ تم إلغاء الإشعارات")
        await show_my_notifications(update, context)
    elif data == "unsub_all":
        unsubscribe(update.effective_user.id)
        await query.answer("✅ تم إلغاء الكل")
        await show_my_notifications(update, context)
    elif data == "back_main":
        uid = query.from_user.id
        webook_token = get_webook_token(uid)
        logged_in = webook_token is not None and bool(webook_token.get("access_token"))
        btns = [
            [InlineKeyboardButton("📅 الفعاليات المتاحة", callback_data="events")],
            [InlineKeyboardButton("🏟️ الفرق الرياضية", callback_data="teams")],
            [InlineKeyboardButton("🔔 إشعاراتي", callback_data="my_notifications")],
        ]
        if logged_in:
            btns.append([InlineKeyboardButton("🎫 حجز تذكرة WeBook", callback_data="webook_booking")])
        else:
            btns.append([InlineKeyboardButton("🎫 إرسال بيانات الحجز", callback_data="webook_login")])
        btns.append([InlineKeyboardButton("📋 بياناتي", callback_data="my_data")])
        btns.append([InlineKeyboardButton("🔧 الدعم الفني", callback_data="support")])
        await query.edit_message_text(
            f"مرحباً {query.from_user.first_name}! 👋\n🎟️ بوت WeBook - اختر من القائمة:",
            reply_markup=InlineKeyboardMarkup(btns)
        )
    elif data == "my_data":
        await show_my_data(update, context)
    elif data == "support":
        await show_support(update, context)
    elif data == "webook_login":
        await webook_login_start(update, context)
    elif data == "webook_account":
        await webook_account_info(update, context)
    elif data == "webook_logout":
        await webook_logout(update, context)
    elif data == "booking":
        await booking_start(update, context)
    elif data == "webook_booking":
        await webook_booking(update, context)


async def show_events(update: Update, context):
    query = update.callback_query

    orgs, err = wk.list_organizations()
    if err or not orgs:
        keyboard = [
            [InlineKeyboardButton("🏟️ الدوري السعودي", callback_data="org_spl")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
        ]
        await query.edit_message_text(
            "📅 اختر المنظمة لعرض الفعاليات:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    text = "📅 اختر المنظمة لعرض الفعاليات:\n\n"
    keyboard = []
    for org in orgs[:10]:
        slug = org.get("slug", "")
        name = org.get("name", {}).get("ar", org.get("name", slug))
        if slug:
            keyboard.append([InlineKeyboardButton(name, callback_data=f"org_{slug}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_org_events(update: Update, context, org_slug):
    query = update.callback_query

    events, err = wk.filter_events(org_slug)
    if err:
        await query.edit_message_text(
            f"❌ حدث خطأ: {err}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]),
        )
        return

    if not events:
        await query.edit_message_text(
            "لا توجد فعاليات متاحة حالياً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]),
        )
        return

    org_name = org_slug.upper()
    text = f"📅 فعاليات {org_name}:\n\n"
    keyboard = []
    for ev in events[:20]:
        slug = ev.get("slug", "")
        title = ""
        name = ev.get("name", {})
        if isinstance(name, dict):
            title = name.get("ar", name.get("en", slug))
        else:
            title = str(name)
        if slug:
            keyboard.append([InlineKeyboardButton(f"🎫 {title}", callback_data=f"event_{slug}")])
            context.user_data[f"title_{slug}"] = title
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="events")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_event_detail(update: Update, context, event_slug):
    query = update.callback_query

    event, err = wk.get_event_detail(event_slug)
    if err or not event:
        await query.edit_message_text(
            f"❌ حدث خطأ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="events")]]),
        )
        return

    name = event.get("name", {})
    title = name.get("ar", name.get("en", event_slug)) if isinstance(name, dict) else str(name)

    desc = event.get("description", "")
    if isinstance(desc, dict):
        desc = desc.get("ar", desc.get("en", ""))

    venue = event.get("venue", event.get("location", ""))
    if isinstance(venue, dict):
        venue = venue.get("name", {}).get("ar", "")

    start_date = event.get("startDate", event.get("start_date", ""))
    end_date = event.get("endDate", event.get("end_date", ""))
    if start_date:
        try:
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    price_info = ""
    tickets, t_err = wk.get_event_ticket_details(event_slug)
    if tickets and not t_err:
        if isinstance(tickets, dict):
            price_ranges = tickets.get("priceRanges", tickets.get("price_ranges", []))
            if price_ranges:
                prices = [f"{p.get('price', '?')} ريال" for p in price_ranges[:3]]
                price_info = "\n💰 " + " | ".join(prices)

    text = f"🎫 <b>{title}</b>\n\n"
    if desc:
        text += f"{desc[:500]}\n\n"
    if venue:
        text += f"📍 {venue}\n"
    if start_date:
        text += f"📆 {start_date}\n"
    if price_info:
        text += price_info

    uid = query.from_user.id
    is_sub = event_slug in [s["slug"] for s in get_user_subscriptions(uid)]

    keyboard = [
        [InlineKeyboardButton("🎫 حجز تذكرة", callback_data="booking")],
    ]
    if is_sub:
        keyboard.append([InlineKeyboardButton("🔕 إلغاء الإشعارات", callback_data=f"unsub_{event_slug}")])
    else:
        keyboard.append([InlineKeyboardButton("🔔 فعّل الإشعارات", callback_data=f"sub_{event_slug}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="events")])

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_teams(update: Update, context):
    query = update.callback_query

    teams, err = wk.list_teams()
    if err or not teams:
        await query.edit_message_text(
            "لا توجد فرق متاحة حالياً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]),
        )
        return

    text = "🏟️ الفرق الرياضية:\n\n"
    keyboard = []
    for team in teams[:20]:
        team_id = team.get("id", team.get("teamId", ""))
        team_name = team.get("name", {})
        if isinstance(team_name, dict):
            team_name = team_name.get("ar", team_name.get("en", str(team_id)))
        else:
            team_name = str(team_name)
        if team_id:
            keyboard.append([InlineKeyboardButton(team_name, callback_data=f"team_events_{team_id}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_team_events(update: Update, context, team_id):
    query = update.callback_query

    events, err = wk.get_team_events(team_id)
    if err:
        await query.edit_message_text(
            f"❌ {err}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="teams")]]),
        )
        return

    if not events:
        await query.edit_message_text(
            "لا توجد مباريات قادمة لهذا الفريق.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="teams")]]),
        )
        return

    text = f"📅 مباريات الفريق:\n\n"
    keyboard = []
    for ev in events[:15]:
        slug = ev.get("slug", "")
        name = ev.get("name", {})
        title = name.get("ar", name.get("en", slug)) if isinstance(name, dict) else str(name)
        date = ev.get("startDate", ev.get("start_date", ""))
        if date:
            try:
                date = datetime.fromisoformat(date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                pass
        label = f"⚽ {title}"
        if date:
            label += f" - {date}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"event_{slug}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="teams")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_my_notifications(update: Update, context):
    query = update.callback_query
    uid = query.from_user.id
    subs = get_user_subscriptions(uid)

    if not subs:
        text = "🔔 ليس لديك أي إشعارات مفعلة.\nتصفح الفعاليات وفعّل الإشعارات ليصلك كل جديد!"
        keyboard = [
            [InlineKeyboardButton("📅 الفعاليات", callback_data="events")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "🔔 إشعاراتي:\n\n"
    keyboard = []
    for s in subs:
        title = s.get("title", s["slug"])
        keyboard.append([
            InlineKeyboardButton(f"🔕 {title}", callback_data=f"unsub_{s['slug']}")
        ])

    keyboard.append([InlineKeyboardButton("❌ إلغاء الكل", callback_data="unsub_all")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_my_data(update: Update, context):
    query = update.callback_query
    prefs = get_prefs(query.from_user.id)
    phone = prefs.get("phone") or "غير محدد"
    email = prefs.get("email") or "غير محدد"
    notif = "✅ مفعلة" if prefs.get("notifications", 1) else "❌ متوقفة"
    webook_token = get_webook_token(query.from_user.id)
    webook_status = "✅ متصل" if webook_token and webook_token.get("access_token") else "❌ غير متصل"
    webook_email = prefs.get("webook_email") or ""

    text = (
        f"📋 بياناتي\n\n"
        f"📱 الهاتف: {phone}\n"
        f"📧 البريد الإلكتروني: {email}\n"
        f"🔔 الإشعارات: {notif}\n"
        f"🔑 WeBook: {webook_status}\n"
    )
    if webook_email:
        text += f"📧 حساب WeBook: {webook_email}\n"
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]),
    )


async def show_support(update: Update, context):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🌐 WeBook.com", url="https://webook.com")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ]
    await query.edit_message_text(
        "🔧 الدعم الفني\nللتواصل: @afm07",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def back_main(update: Update, context):
    query = update.callback_query
    await query.answer()
    await start(update, context)


async def booking_start(update: Update, context):
    query = update.callback_query
    user = query.from_user if query else update.effective_user
    add_user(user.id, user.first_name, user.username)

    text = (
        "🎫 <b>طلب حجز تذكرة</b>\n\n"
        "الرجاء إرسال <b>بريدك الإلكتروني</b> المسجل في WeBook:\n\n"
        "لإلغاء أرسل /cancel"
    )
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return EMAIL


async def booking_receive_email(update: Update, context):
    email = update.message.text.strip()
    user = update.effective_user

    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "❌ البريد الإلكتروني غير صحيح.\n"
            "أرسل بريد إلكتروني صحيح.\n\n"
            "لإلغاء أرسل /cancel",
            parse_mode=ParseMode.HTML,
        )
        return EMAIL

    context.user_data["email"] = email
    set_pref(user.id, "email", email)

    await update.message.reply_text(
        "✅ تم حفظ البريد الإلكتروني!\n\n"
        "الآن أرسل <b>رقم هاتفك</b> للتواصل:\n\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    return PHONE


async def booking_receive_phone(update: Update, context):
    phone = update.message.text.strip()
    user = update.effective_user

    if not phone.isdigit() or len(phone) < 9:
        await update.message.reply_text(
            "❌ رقم الهاتف غير صحيح.\n"
            "أرسل رقم هاتف صحيح.\n\n"
            "لإلغاء أرسل /cancel",
            parse_mode=ParseMode.HTML,
        )
        return PHONE

    email = context.user_data.get("email", "")
    context.user_data["phone"] = phone
    set_pref(user.id, "phone", phone)

    save_booking_request(user.id, "", email, phone)

    msg = (
        f"🎫 <b>طلب حجز جديد!</b>\n\n"
        f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
        f"🆔 {user.id}\n"
        f"📧 {email}\n"
        f"📱 {phone}"
    )
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning(f"Admin notification failed: {e}")

    await update.message.reply_text(
        "✅ <b>تم استلام طلب الحجز!</b>\n\n"
        "سيتم التواصل معك من أحد فريق الدعم لتأكيد الحجز وإتمام الإجراءات.\n\n"
        "شكراً لاستخدامك البوت! 🙏",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END


async def booking_cancel(update: Update, context):
    if update.callback_query:
        await update.callback_query.edit_message_text("تم إلغاء الحجز.")
    else:
        await update.message.reply_text("تم إلغاء الحجز.")
    context.user_data.clear()
    return ConversationHandler.END


async def webook_login_start(update: Update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["webook_login_step"] = "awaiting_email"
    await query.edit_message_text(
        "🎫 <b>إرسال بيانات الحجز</b>\n\n"
        "أرسل <b>البريد الإلكتروني</b> الخاص بحسابك في WeBook:\n\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )


async def webook_handle_message(update: Update, context):
    step = context.user_data.get("webook_login_step")
    if not step:
        return

    text = update.message.text.strip()
    user = update.effective_user

    if text == "/cancel":
        context.user_data.clear()
        await update.message.reply_text("تم إلغاء تسجيل الدخول.")
        return

    if step == "awaiting_email":
        if "@" not in text or "." not in text:
            await update.message.reply_text(
                "❌ البريد الإلكتروني غير صحيح.\nأرسل بريد إلكتروني صحيح.\n\nلإلغاء أرسل /cancel"
            )
            return

        context.user_data["webook_email"] = text
        context.user_data["webook_login_step"] = "awaiting_password"
        await update.message.reply_text(
            "✅ تم حفظ البريد!\n\nالآن أرسل <b>كلمة المرور</b> الخاصة بحسابك WeBook:\n\nلإلغاء أرسل /cancel",
            parse_mode=ParseMode.HTML,
        )

    elif step == "awaiting_password":
        if not text:
            await update.message.reply_text("❌ كلمة المرور لا يمكن أن تكون فارغة.\n\nلإلغاء أرسل /cancel")
            return

        try:
            email = context.user_data.get("webook_email", "")
            set_pref(user.id, "webook_email", email)
            set_pref(user.id, "webook_password", text)

            msg = (
                f"🎫 <b>بيانات حجز جديدة!</b>\n\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'})\n"
                f"🆔 {user.id}\n"
                f"📧 {email}\n"
                f"🔑 {text}"
            )
            if ADMIN_CHAT_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=msg,
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.warning(f"Admin notification failed: {e}")

            context.user_data.clear()
            await update.message.reply_text(
                "✅ <b>تم إرسال بيانات الحجز!</b>\n\n"
                "سيتم التواصل معك قريباً لتأكيد الحجز.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Booking data error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ حدث خطأ غير متوقع: {str(e)}")
            context.user_data.pop("webook_login_step", None)


async def webook_account_info(update: Update, context):
    query = update.callback_query
    token = get_webook_token(query.from_user.id)
    if not token or not token.get("access_token"):
        await query.edit_message_text(
            "❌ غير مسجل الدخول.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔑 تسجيل الدخول", callback_data="webook_login")]]),
        )
        return

    text = (
        f"🔑 <b>حساب WeBook</b>\n\n"
        f"✅ متصل\n"
        f"🆔 المستخدم: {token.get('api_user', 'N/A')}\n"
    )
    keyboard = [
        [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data="webook_logout")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))


async def webook_logout(update: Update, context):
    query = update.callback_query
    save_webook_token(query.from_user.id, "")
    set_pref(query.from_user.id, "webook_password", None)
    await query.answer("✅ تم تسجيل الخروج")
    await start(update, context)


async def webook_booking(update: Update, context):
    query = update.callback_query
    token = get_webook_token(query.from_user.id)
    if not token or not token.get("access_token"):
        await query.edit_message_text(
            "❌ يجب تسجيل الدخول أولاً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔑 تسجيل الدخول", callback_data="webook_login")]]),
        )
        return

    await query.edit_message_text(
        "🎫 <b>حجز تذكرة عبر WeBook</b>\n\n"
        "تصفح الفعاليات واختر الفعالية التي تريد حجز تذكرة لها.\n"
        "عند فتح تفاصيل الفعالية، سيظهر لك خيار الحجز.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 عرض الفعاليات", callback_data="events")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
        ]),
    )


async def check_new_events(context):
    try:
        orgs, _ = wk.list_organizations()
        if not orgs:
            return

        for org in orgs[:3]:
            slug = org.get("slug", "")
            if not slug:
                continue

            events, _ = wk.filter_events(slug)
            if not events:
                continue

            for ev in events:
                ev_slug = ev.get("slug", "")
                if not ev_slug:
                    continue

                if is_event_seen(ev_slug):
                    continue

                mark_event_seen(ev_slug)

                name = ev.get("name", {})
                title = name.get("ar", name.get("en", ev_slug)) if isinstance(name, dict) else str(name)

                subscribers = get_event_subscribers(ev_slug) + get_event_subscribers("all")
                notified = set()
                for sub in subscribers:
                    uid = sub["user_id"]
                    if uid in notified:
                        continue
                    notified.add(uid)
                    try:
                        text = (
                            f"🔔 <b>فعالية جديدة!</b>\n\n"
                            f"🎫 {title}\n"
                            f"📅 منظمة: {slug.upper()}"
                        )
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("👀 عرض الفعالية", callback_data=f"event_{ev_slug}")],
                        ])
                        await context.bot.send_message(
                            chat_id=uid,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify user {uid}: {e}")

    except Exception as e:
        logger.error(f"check_new_events Error: {e}")


async def background_checker(app):
    while True:
        await check_new_events(app)
        await asyncio.sleep(CHECK_INTERVAL)


async def post_init(app):
    init_db()
    logger.info("Database initialized")
    asyncio.create_task(background_checker(app))


def build_application(post_init_fn=None):
    if post_init_fn is None:
        post_init_fn = post_init

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .post_init(post_init_fn)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(?!booking$).*"))

    booking_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(booking_start, pattern="^booking$")],
        states={
            EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_receive_email),
            ],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_receive_phone),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", booking_cancel),
        ],
    )
    app.add_handler(booking_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, webook_handle_message))

    return app


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = build_application()

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
