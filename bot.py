import html
import logging
import re
from decimal import Decimal
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import db
import userbot
from config import ADMIN_IDS, BIO_TAG, BOT_TOKEN, FEE_WITH_TAG, FEE_WITHOUT_TAG
from form import DealForm, fmt_amount, parse_form

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

_BIO_TAG_RE = re.compile(rf"(?<!\w){re.escape(BIO_TAG)}(?!\w)", re.IGNORECASE)


def is_admin(user_id: Optional[int]) -> bool:
    return user_id in ADMIN_IDS


def profile_link(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'


def has_bio_tag(bio: str) -> bool:
    return bool(_BIO_TAG_RE.search(bio or ""))


def deal_fee(seller: userbot.UserInfo, buyer: userbot.UserInfo) -> Decimal:
    return FEE_WITH_TAG if has_bio_tag(seller.bio) and has_bio_tag(buyer.bio) else FEE_WITHOUT_TAG


def render_deal_card(
    deal_id: str, escrower_id: int, escrower_name: str,
    seller: userbot.UserInfo, buyer: userbot.UserInfo, amount: Decimal, fee: Decimal,
) -> str:
    return (
        f"{E_TITLE} <b>Escrow Deal [strawHats]</b>\n\n"
        f"{E_ID} <b>Deal ID</b> - <code>{deal_id}</code>\n"
        f"{E_ESCROWER} <b>Escrower</b> - {profile_link(escrower_id, escrower_name)}\n"
        f"{E_PARTY} <b>Seller</b> - {profile_link(seller.id, seller.first_name)} [<code>{seller.id}</code>]\n"
        f"{E_PARTY} <b>Buyer</b> - {profile_link(buyer.id, buyer.first_name)} [<code>{buyer.id}</code>]\n"
        f"{E_AMOUNT} <b>Amount</b> - ${fmt_amount(amount)}\n"
        f"{E_FEES} <b>Total Fees</b> - ${fee:.2f}\n\n"
        f"{E_RELEASE} <b>${fmt_amount(amount - fee)} to be released!</b>"
    )


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not is_admin(user.id):
        return

    form_msg = msg.reply_to_message
    if not form_msg:
        await msg.reply_text("Reply to a filled deal form with /add")
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
    if form.amount <= fee:
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
        amount=str(form.amount),
        fee=str(fee),
        method=form.method,
        fee_by=form.fee_by,
        terms=form.terms,
    )
    card = await form_msg.reply_text(
        render_deal_card(deal_id, user.id, user.first_name, seller, buyer, form.amount, fee),
        parse_mode=ParseMode.HTML,
    )
    db.set_card_msg(deal_id, card.message_id)
    log.info("Deal %s created by %s in chat %s", deal_id, user.id, msg.chat_id)


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
    app.add_handler(CommandHandler("add", add_cmd))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
