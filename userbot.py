import logging
from dataclasses import dataclass
from typing import Optional

from config import API_HASH, API_ID, USERBOT_SESSION

log = logging.getLogger(__name__)
_client = None


@dataclass
class UserInfo:
    id: int
    first_name: str
    username: str
    bio: str


def is_connected() -> bool:
    return _client is not None


async def start() -> None:
    global _client
    if not (API_ID and API_HASH):
        log.warning("Userbot disabled (API_ID/API_HASH not set)")
        return
    from telethon import TelegramClient

    client = TelegramClient(USERBOT_SESSION, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        log.warning("Userbot session not logged in; run: python3 login_userbot.py")
        await client.disconnect()
        return
    me = await client.get_me()
    log.info("Userbot connected as %s (%s)", me.username or me.first_name, me.id)
    _client = client


async def stop() -> None:
    if _client:
        await _client.disconnect()


async def lookup(username: str) -> Optional[UserInfo]:
    """Resolve @username to id, first name and current bio via the userbot."""
    if not _client:
        return None
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.types import User

    try:
        entity = await _client.get_entity(username.lstrip("@"))
        if not isinstance(entity, User):
            return None
        full = await _client(GetFullUserRequest(entity))
    except Exception as exc:
        log.info("Userbot could not resolve @%s: %s", username, exc)
        return None
    return UserInfo(
        id=entity.id,
        first_name=entity.first_name or entity.username or str(entity.id),
        username=entity.username or username.lstrip("@"),
        bio=full.full_user.about or "",
    )
