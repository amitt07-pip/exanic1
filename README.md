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
