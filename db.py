import sqlite3
import time
from typing import Optional

from config import DB_PATH, DEAL_ID_PREFIX, DEAL_ID_START

_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS deals (
        num INTEGER PRIMARY KEY,
        deal_id TEXT UNIQUE NOT NULL,
        chat_id INTEGER NOT NULL,
        form_msg_id INTEGER NOT NULL,
        card_msg_id INTEGER,
        escrower_id INTEGER NOT NULL,
        escrower_name TEXT,
        seller_username TEXT,
        seller_id INTEGER,
        seller_name TEXT,
        buyer_username TEXT,
        buyer_id INTEGER,
        buyer_name TEXT,
        amount TEXT NOT NULL,
        form_amount TEXT,
        fee TEXT NOT NULL,
        method TEXT,
        fee_by TEXT,
        terms TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at INTEGER NOT NULL,
        confirmed_by INTEGER,
        confirmed_at INTEGER,
        confirm_msg_id INTEGER,
        result TEXT,
        closed_by INTEGER,
        closed_at INTEGER,
        UNIQUE (chat_id, form_msg_id)
    );
    """
)
_deal_cols = {r["name"] for r in _conn.execute("PRAGMA table_info(deals)")}
for _col, _type in (
    ("form_amount", "TEXT"), ("confirmed_by", "INTEGER"), ("confirmed_at", "INTEGER"),
    ("confirm_msg_id", "INTEGER"), ("result", "TEXT"), ("closed_by", "INTEGER"), ("closed_at", "INTEGER"),
):
    if _col not in _deal_cols:
        _conn.execute(f"ALTER TABLE deals ADD COLUMN {_col} {_type}")
_conn.commit()


def deal_for_form(chat_id: int, form_msg_id: int) -> Optional[sqlite3.Row]:
    return _conn.execute(
        "SELECT * FROM deals WHERE chat_id = ? AND form_msg_id = ?", (chat_id, form_msg_id)
    ).fetchone()


def create_deal(**fields) -> str:
    with _conn:
        row = _conn.execute("SELECT MAX(num) AS n FROM deals").fetchone()
        num = max(DEAL_ID_START, (row["n"] or 0) + 1)
        deal_id = f"{DEAL_ID_PREFIX}-{num}"
        fields.update(num=num, deal_id=deal_id, created_at=int(time.time()))
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        _conn.execute(f"INSERT INTO deals ({cols}) VALUES ({marks})", tuple(fields.values()))
    return deal_id


def set_card_msg(deal_id: str, card_msg_id: int) -> None:
    _conn.execute("UPDATE deals SET card_msg_id = ? WHERE deal_id = ?", (card_msg_id, deal_id))
    _conn.commit()


def get_deal(deal_id: str) -> Optional[sqlite3.Row]:
    return _conn.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()


def finish_deal(deal_id: str, result: str, user_id: int) -> bool:
    """Mark an active deal released/refunded; False if it was already confirmed."""
    with _conn:
        cur = _conn.execute(
            "UPDATE deals SET status = 'confirmed', result = ?, confirmed_by = ?, confirmed_at = ? "
            "WHERE deal_id = ? AND status = 'active'",
            (result, user_id, int(time.time()), deal_id),
        )
    return cur.rowcount == 1


def set_confirm_msg(deal_id: str, msg_id: int) -> None:
    _conn.execute("UPDATE deals SET confirm_msg_id = ? WHERE deal_id = ?", (msg_id, deal_id))
    _conn.commit()


def deal_for_message(chat_id: int, msg_id: int) -> Optional[sqlite3.Row]:
    return _conn.execute(
        "SELECT * FROM deals WHERE chat_id = ? AND ? IN (card_msg_id, confirm_msg_id, form_msg_id)",
        (chat_id, msg_id),
    ).fetchone()


def complete_deal(deal_id: str, admin_id: int) -> bool:
    with _conn:
        cur = _conn.execute(
            "UPDATE deals SET status = 'completed', closed_by = ?, closed_at = ? "
            "WHERE deal_id = ? AND status = 'confirmed'",
            (admin_id, int(time.time()), deal_id),
        )
    return cur.rowcount == 1
