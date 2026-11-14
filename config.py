import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _ids(value: str) -> set[int]:
    return {int(x) for x in value.replace(" ", "").split(",") if x}


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = _ids(os.getenv("ADMIN_IDS", "") or "7309945816,8813683639,8492251668,6401798917,6103268316")
CHAT_GROUP_ID = int(os.getenv("CHAT_GROUP_ID", "") or -1004482395935)
JOIN_LOG_CHAT_ID = int(os.getenv("JOIN_LOG_CHAT_ID", "") or -1004422716732)
ESCROW_GROUP_LIST = [
    int(x) for x in (os.getenv("ESCROW_GROUP_IDS", "") or "-1004341809670,-1004422790680").replace(" ", "").split(",") if x
]
ESCROW_GROUP_IDS = set(ESCROW_GROUP_LIST)
ALLOWED_GROUP_IDS = ESCROW_GROUP_IDS | {CHAT_GROUP_ID}
DEAL_ID_PREFIX = "SH"
DEAL_ID_START = int(os.getenv("DEAL_ID_START", "") or 65303)
DB_PATH = BASE_DIR / os.getenv("DB_FILE", "escrow.db")

BIO_TAG = "@exanic"
# Per escrow group (in ESCROW_GROUP_IDS order): fee per person when both bios have BIO_TAG,
# up to the amount cap; above it a % per person; without both tags a flat % of the deal.
FEE_RULES = [
    {"per_person": Decimal("0.50"), "cap": Decimal("1500"), "pct_per_person": Decimal("0.0005"), "pct_no_tag": Decimal("0.005")},
    {"per_person": Decimal("1.00"), "cap": Decimal("2000"), "pct_per_person": Decimal("0.001"), "pct_no_tag": Decimal("0.01")},
]
GROUP_FEE_RULES = dict(zip(ESCROW_GROUP_LIST, FEE_RULES))

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
USERBOT_SESSION = str(BASE_DIR / os.getenv("USERBOT_SESSION", "userbot_session"))
