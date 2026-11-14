# exanic1

Telegram escrow bot (python-telegram-bot + Telethon userbot, SQLite).

## Setup

```
cd /root/exanic1
pip install -r requirements.txt
cp .env.example .env   # fill BOT_TOKEN, ADMIN_IDS, API_ID, API_HASH
python3 login_userbot.py   # one-time userbot login (phone + code)
cp exanic.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now exanic
```

## Groups

The bot ignores every group except `CHAT_GROUP_ID` (default -1004482395935) and `ESCROW_GROUP_IDS`. Deal commands (`/add`, `/close`) only work in `ESCROW_GROUP_IDS`, never in the chat group.

## Commands (escrowers in ADMIN_IDS)

- `/add [received amount]` — reply to a deal form (amount optional; defaults to the form amount):

```
Seller - @seller
Buyer - @buyer
Amount in $ - 100
[MUST]Payment Method - upi
[MUST]Fee By - buyer
Terms - optional
```

Fee is $1.00 when both seller and buyer have `@exanic` in their bio, otherwise $2.00.

The deal card has **✅ Close** (release to buyer) and **🛑 Cancel** (refund to seller) buttons, Close can only be tapped by the seller and Cancel only by the buyer; each deal can be closed once.

- `/close` — the escrower who started the deal replies to the deal card (or the CONFIRMED message) after release/refund is confirmed; the bot deletes the command, marks the deal completed and asks both parties to vouch. The bot needs *Delete messages* admin rights.
- `/stats`, `/stats @username`, or reply `/stats` — anyone, chat group only; shows completed-deal stats. Own `/stats` has a **📊 My Panel** button that opens `/panel` in the bot DM.
- `/panel` (DM only) — escrow dashboard; only ❌ Close works for now.
- `/clonestats @username | user id`, or reply `/clonestats` (admins only) — bot asks for the stats format; the sent values replace that user's `/stats` (deals completed afterwards are added on top).
- Address tracking — after Close/Cancel is confirmed, when the deal's buyer or seller sends a wallet address / UPI ID in the escrow group, the bot replies **✅ Address Tracked** with a per-address count (first time random 30–40, then +1 each time) and a **📋 PREVIOUS OCCURRENCES** button that disappears when the sender taps it.
- Join notices — when someone joins the chat group, the bot posts `~ @user (id) has been added by @actor (id) in the strawHats Group ‼️` to `JOIN_LOG_CHAT_ID` (default -1004422716732). If that user later leaves, is kicked or banned, the notice is struck through. The bot must be admin in the chat group and able to post in the log chat.
- `/setupaddy` (escrowers only) — buttons pick token (USDT) and network (BSC/BEP20 or TRX/TRC20), then the escrower sends the address and the bot saves it.
- `/verify <address>` (or reply `/verify` to a message with the address) — anyone; if the address is a saved escrower address the bot replies **Address Belongs to Escrower** with the escrower's name; otherwise it replies **WARNING: Unverified Address**.
- Filters (Rose-style) — escrowers set them in the bot DM; they trigger only in the chat group. `/filter <keyword> <reply>` or reply to a message (text/photo/video/GIF/document/audio/voice/sticker) with `/filter <keyword>`; `"quotes"` for multi-word keywords. `/filters` lists, `/stop <keyword>` removes one, `/stopall` removes all. Any chat group message containing the keyword (whole word, any case) gets the reply. Reply text supports `{first}`, `{mention}`, `{username}`, `{id}`. Buttons: `[Text](buttonurl://example.com)` adds a URL button on a new row; `[Text](buttonurl://example.com:same)` puts it on the same row as the previous one.
- `/mydeals` — anyone, escrow groups only; the bot deletes the command and lists the sender's active (not yet `/close`d) deals: deal ID linked to the deal card, role and release amount, plus one button per deal opening the original form.
