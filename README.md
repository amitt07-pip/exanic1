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

The deal card has **✅ Close** (release to buyer) and **🛑 Cancel** (refund to seller) buttons, usable by escrowers only; each deal can be closed once.
