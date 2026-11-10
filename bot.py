import html
import logging
import random
import re
from decimal import Decimal
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application, ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, TypeHandler,
    filters,
)

import db
import userbot
from config import ADMIN_IDS, ALLOWED_GROUP_IDS, BIO_TAG, CHAT_GROUP_ID, BOT_TOKEN, ESCROW_GROUP_IDS, FEE_WITH_TAG, FEE_WITHOUT_TAG
from form import fmt_amount, parse_form, parse_number, parse_stats

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("exanic")


def emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


E_TITLE = emoji("5850633746583129853", "🛡")
E_ID = emoji("5257965174979042426", "🆔")
E_ESCROWER = emoji("5920052658743283381", "👤")
E_PARTY = emoji("5936130851635990622", "👤")
E_AMOUNT = emoji("5992430854909989581", "💵")
E_FEES = emoji("5913702317667913862", "💰")
E_RELEASE = emoji("5985596818912712352", "📤")
E_CUT = emoji("6007895992760799065", "✂️")
E_CONFIRMED = emoji("5942678061127306511", "✅")
E_CONFIRM_ESCROWER = emoji("5771695636411847302", "👤")
E_RECEIVER = emoji("5967548335542767952", "💸")
E_CLOSED = emoji("5260416304224936047", "✅")
E_VOUCH = emoji("5258204546391351475", "⭐")

E_STATS = emoji("5258011929993026890", "📊")
E_NAME = emoji("5877465816030515018", "👤")
E_USER_ID = emoji("5771887475421090729", "🆔")
E_TOTAL = emoji("5926783847453692661", "🤝")
E_ESCROWED = emoji("5778423822940114949", "💰")
E_LARGEST = emoji("5992430854909989581", "💵")
E_RANK = emoji("5931472654660800739", "🏆")
E_RATE = emoji("5985596818912712352", "✅")

_BIO_TAG_RE = re.compile(rf"(?<!\w){re.escape(BIO_TAG)}(?!\w)", re.IGNORECASE)


def is_admin(user_id: Optional[int]) -> bool:
    return user_id in ADMIN_IDS


async def only_allowed_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.type != "private" and chat.id not in ALLOWED_GROUP_IDS:
        raise ApplicationHandlerStop


def profile_link(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'


def has_bio_tag(bio: str) -> bool:
    return bool(_BIO_TAG_RE.search(bio or ""))


def deal_fee(seller: userbot.UserInfo, buyer: userbot.UserInfo) -> Decimal:
    return FEE_WITH_TAG if has_bio_tag(seller.bio) and has_bio_tag(buyer.bio) else FEE_WITHOUT_TAG


def render_deal_card(
    deal_id: str, escrower_id: int, escrower_name: str,
    seller: userbot.UserInfo, buyer: userbot.UserInfo, amount: Decimal, fee: Decimal, form_amount: Decimal,
) -> str:
    text = (
        f"{E_TITLE} <b>Escrow Deal [strawHats]</b>\n\n"
        f"{E_ID} <b>Deal ID</b> - <code>{deal_id}</code>\n"
        f"{E_ESCROWER} <b>Escrower</b> - {profile_link(escrower_id, escrower_name)}\n"
        f"{E_PARTY} <b>Seller</b> - {profile_link(seller.id, seller.first_name)} [<code>{seller.id}</code>]\n"
        f"{E_PARTY} <b>Buyer</b> - {profile_link(buyer.id, buyer.first_name)} [<code>{buyer.id}</code>]\n"
        f"{E_AMOUNT} <b>Amount</b> - ${fmt_amount(amount)}\n"
        f"{E_FEES} <b>Total Fees</b> - ${fee:.2f}\n\n"
        f"{E_RELEASE} <b>${fmt_amount(amount - fee)} to be released!</b>"
    )
    if amount < form_amount:
        text += f"\n\n{E_CUT} Cut ${form_amount - amount:.2f} from ${fmt_amount(form_amount)}."
    return text


def deal_buttons(deal_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Close", callback_data=f"deal:release:{deal_id}"),
        InlineKeyboardButton("🛑 Cancel", callback_data=f"deal:refund:{deal_id}"),
    ]])


def render_confirmed(deal, action: str) -> str:
    title, role, username = (
        ("Release", "Buyer", deal["buyer_username"]) if action == "release"
        else ("Refund", "Seller", deal["seller_username"])
    )
    return (
        f"{E_CONFIRMED} <b>{title} CONFIRMED!</b>\n\n"
        f"{E_ID} <b>Deal ID</b> - <code>{deal['deal_id']}</code>\n"
        f"{E_CONFIRM_ESCROWER} <b>Escrower</b> : {profile_link(deal['escrower_id'], deal['escrower_name'])}\n\n"
        f"{E_RECEIVER} <b>{role}</b> : @{html.escape(username)} - receive your funds."
    )


async def deal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, action, deal_id = query.data.split(":", 2)
    deal = db.get_deal(deal_id)
    allowed_id = deal and (deal["seller_id"] if action == "release" else deal["buyer_id"])
    if not deal or query.from_user.id != allowed_id:
        await query.answer()
        return
    if not db.finish_deal(deal_id, "released" if action == "release" else "refunded", query.from_user.id):
        await query.answer(f"Deal already {db.get_deal(deal_id)['result']}.", show_alert=True)
        return
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except TelegramError as exc:
        log.info("Could not remove buttons for %s: %s", deal_id, exc)
    sent = await query.message.reply_text(render_confirmed(deal, action), parse_mode=ParseMode.HTML)
    db.set_confirm_msg(deal_id, sent.message_id)
    log.info("Deal %s %s by %s", deal_id, action, query.from_user.id)


def render_completed(deal) -> str:
    vouch = f"Vouch @Exanic for ${fmt_amount(Decimal(deal['amount']))} deal, safely escrowed."
    return (
        f"{E_CLOSED} <b>Deal</b> <code>{deal['deal_id']}</code> <b>has been closed!</b>\n"
        f"~ {profile_link(deal['buyer_id'], deal['buyer_name'])} and "
        f"{profile_link(deal['seller_id'], deal['seller_name'])} are requested to drop the vouch before leaving.\n\n"
        f"{E_VOUCH} <code>{html.escape(vouch)}</code>"
    )


async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return
    target = msg.reply_to_message
    deal = db.deal_for_message(msg.chat_id, target.message_id) if target else None
    if not deal or deal["escrower_id"] != user.id:
        return
    if deal["status"] == "active":
        await msg.reply_text("Seller/Buyer must confirm release or refund first.")
        return
    if not db.complete_deal(deal["deal_id"], user.id):
        await msg.reply_text(
            f"Deal <code>{deal['deal_id']}</code> is already closed.", parse_mode=ParseMode.HTML
        )
        return
    try:
        await msg.delete()
    except TelegramError as exc:
        log.info("Could not delete /close message: %s", exc)
    await target.reply_text(render_completed(deal), parse_mode=ParseMode.HTML)
    log.info("Deal %s completed by %s", deal["deal_id"], user.id)


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return

    form_msg = msg.reply_to_message
    if not form_msg:
        await msg.reply_text("Reply to a filled deal form with /add [received amount]")
        return

    received = None
    if context.args:
        received = parse_number(" ".join(context.args))
        if received is None:
            await msg.reply_text("Usage: reply to the form with /add [received amount], e.g. /add 100")
            return

    form, problems = parse_form(form_msg.text or form_msg.caption)
    if not form:
        await msg.reply_text("Invalid deal form. Missing or wrong:\n• " + "\n• ".join(problems))
        return

    existing = db.deal_for_form(msg.chat_id, form_msg.message_id)
    if existing:
        await msg.reply_text(
            f"This form is already added as <code>{existing['deal_id']}</code>.", parse_mode=ParseMode.HTML
        )
        return

    if not userbot.is_connected():
        await msg.reply_text("Userbot is not connected. Run: python3 login_userbot.py and restart the bot.")
        return

    seller = await userbot.lookup(form.seller)
    buyer = await userbot.lookup(form.buyer)
    unresolved = [f"@{u}" for u, info in ((form.seller, seller), (form.buyer, buyer)) if not info]
    if unresolved:
        await msg.reply_text("Could not find user: " + ", ".join(unresolved))
        return

    fee = deal_fee(seller, buyer)
    amount = received if received is not None else form.amount
    if amount <= fee:
        await msg.reply_text(f"Amount must be more than the ${fee:.2f} fee.")
        return

    deal_id = db.create_deal(
        chat_id=msg.chat_id,
        form_msg_id=form_msg.message_id,
        escrower_id=user.id,
        escrower_name=user.first_name,
        seller_username=seller.username,
        seller_id=seller.id,
        seller_name=seller.first_name,
        buyer_username=buyer.username,
        buyer_id=buyer.id,
        buyer_name=buyer.first_name,
        amount=str(amount),
        form_amount=str(form.amount),
        fee=str(fee),
        method=form.method,
        fee_by=form.fee_by,
        terms=form.terms,
    )
    card = await form_msg.reply_text(
        render_deal_card(deal_id, user.id, user.first_name, seller, buyer, amount, fee, form.amount),
        parse_mode=ParseMode.HTML,
        reply_markup=deal_buttons(deal_id),
    )
    db.set_card_msg(deal_id, card.message_id)
    log.info("Deal %s created by %s in chat %s", deal_id, user.id, msg.chat_id)


def fmt_usd(value: float) -> str:
    """10000 -> 10,000.00, 100 -> 100.0"""
    return f"{value:,.2f}" if value >= 1000 else fmt_amount(Decimal(str(value)))


def success_rate(user_id: int) -> float:
    return round(random.Random(user_id).uniform(80, 90), 1)


def render_stats(user_id: int, name: str) -> str:
    st = db.user_stats(user_id)
    rate = st["rate"] if st["rate"] is not None else success_rate(user_id)
    return (
        f"{E_STATS} <b>Escrow Stats :</b>\n\n"
        f"{E_NAME} <b>Name:</b> {profile_link(user_id, name)}\n"
        f"{E_USER_ID} <b>User ID:</b> <code>{user_id}</code>\n"
        f"{E_TOTAL} <b>Total Escrows:</b> {st['count']}\n"
        f"{E_ESCROWED} <b>Escrowed Amount:</b> ${fmt_usd(st['total'])}\n"
        f"{E_LARGEST} <b>Largest Deal:</b> ${fmt_usd(st['largest'])}\n"
        f"{E_RANK} <b>Rank:</b> #{st['rank']}\n"
        f"{E_RATE} <b>Success Rate:</b> {rate:.1f}%"
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    markup = None
    if context.args:
        username = context.args[0]
        if not userbot.is_connected():
            await msg.reply_text("Userbot is not connected. Run: python3 login_userbot.py and restart the bot.")
            return
        info = await userbot.lookup(username)
        if not info:
            await msg.reply_text(f"Could not find user: @{username.lstrip('@')}")
            return
        target_id, name = info.id, info.first_name
    elif msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        target_id, name = target.id, target.first_name
    else:
        target_id, name = user.id, user.first_name
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 My Panel", url=f"https://t.me/{context.bot.username}?start=panel")
        ]])
    await msg.reply_text(render_stats(target_id, name), parse_mode=ParseMode.HTML, reply_markup=markup)


CLONE_TEMPLATE = (
    "Total Escrows: \n"
    "Escrowed Amount: $\n"
    "Largest Deal: $\n"
    "Rank: #\n"
    "Success Rate: %"
)


async def target_from_args(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[tuple[int, str]]:
    """(user_id, first name) from @username / user id argument or the replied-to message."""
    msg = update.effective_message
    if context.args:
        arg = context.args[0]
        if arg.lstrip("-").isdigit():
            user_id = int(arg)
            try:
                chat = await context.bot.get_chat(user_id)
                return user_id, chat.first_name or str(user_id)
            except TelegramError:
                return user_id, str(user_id)
        if not userbot.is_connected():
            await msg.reply_text("Userbot is not connected. Run: python3 login_userbot.py and restart the bot.")
            return None
        info = await userbot.lookup(arg)
        if not info:
            await msg.reply_text(f"Could not find user: @{arg.lstrip('@')}")
            return None
        return info.id, info.first_name
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        return target.id, target.first_name
    await msg.reply_text("Usage: /clonestats @username | user id, or reply to the user")
    return None


async def clonestats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return
    target = await target_from_args(update, context)
    if not target:
        return
    context.bot_data.setdefault("clone_pending", {})[(msg.chat_id, user.id)] = target
    await msg.reply_text(
        f"Send the new stats for {profile_link(*target)} [<code>{target[0]}</code>] in this format:\n\n"
        f"<code>{CLONE_TEMPLATE}</code>",
        parse_mode=ParseMode.HTML,
    )


async def clonestats_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return
    pending = context.bot_data.get("clone_pending", {})
    target = pending.get((msg.chat_id, user.id))
    if not target:
        return
    values, bad = parse_stats(msg.text)
    if bad:
        await msg.reply_text("Missing or invalid: " + ", ".join(bad) + "\nSend the stats again.")
        return
    pending.pop((msg.chat_id, user.id), None)
    db.save_cloned_stats(target[0], values, user.id)
    await msg.reply_text(render_stats(*target), parse_mode=ParseMode.HTML)
    log.info("Stats for %s cloned by %s", target[0], user.id)


PANEL_TEXT = (
    "👤 <b>Your Escrow Dashboard</b>\n\n"
    "Track your trade history, live deals, fees, and favourite partners — all in one place."
)


def panel_buttons() -> InlineKeyboardMarkup:
    def b(text: str, key: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text, callback_data=f"panel:{key}")

    return InlineKeyboardMarkup([
        [b("📊 My Volume", "volume"), b("💸 Fees Paid", "fees")],
        [b("📦 Ongoing Deals", "ongoing")],
        [b("📦 Fav Partner", "partner"), b("⭐️ Fav Escrower", "escrower")],
        [b("❌ Close", "close")],
    ])


async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(PANEL_TEXT, parse_mode=ParseMode.HTML, reply_markup=panel_buttons())


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args and context.args[0].lower() == "panel":
        await panel_cmd(update, context)


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "panel:close":
        await query.edit_message_text("✅ Panel closed.")


async def post_init(app: Application) -> None:
    await userbot.start()


async def post_shutdown(app: Application) -> None:
    await userbot.stop()


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN missing in .env")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    escrow_groups = filters.Chat(ESCROW_GROUP_IDS)
    app.add_handler(TypeHandler(Update, only_allowed_groups), group=-1)
    app.add_handler(CommandHandler("add", add_cmd, filters=escrow_groups))
    app.add_handler(CommandHandler("close", close_cmd, filters=escrow_groups))
    app.add_handler(CallbackQueryHandler(deal_callback, pattern=r"^deal:(release|refund):"))
    app.add_handler(CommandHandler("stats", stats_cmd, filters=filters.Chat(CHAT_GROUP_ID)))
    app.add_handler(CommandHandler("panel", panel_cmd, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("start", start_cmd, filters=filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern=r"^panel:"))
    app.add_handler(CommandHandler(["clonestats", "clonestat"], clonestats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, clonestats_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
