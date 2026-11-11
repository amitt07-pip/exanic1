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
ESCROW_GROUP_IDS = _ids(os.getenv("ESCROW_GROUP_IDS", "") or "-1004341809670,-1004422790680")
ALLOWED_GROUP_IDS = ESCROW_GROUP_IDS | {CHAT_GROUP_ID}
DEAL_ID_PREFIX = "SH"
DEAL_ID_START = int(os.getenv("DEAL_ID_START", "") or 65303)
DB_PATH = BASE_DIR / os.getenv("DB_FILE", "escrow.db")

BIO_TAG = "@exanic"
FEE_WITH_TAG = Decimal("1.00")
FEE_WITHOUT_TAG = Decimal("2.00")

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
USERBOT_SESSION = str(BASE_DIR / os.getenv("USERBOT_SESSION", "userbot_session"))
