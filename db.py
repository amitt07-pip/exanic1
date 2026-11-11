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
    CREATE TABLE IF NOT EXISTS tracked_addresses (
        address TEXT PRIMARY KEY,
        count INTEGER NOT NULL,
        first_user_id INTEGER,
        updated_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS join_notices (
        user_id INTEGER PRIMARY KEY,
        chat_id INTEGER NOT NULL,
        msg_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS cloned_stats (
        user_id INTEGER PRIMARY KEY,
        total INTEGER NOT NULL,
        worth REAL NOT NULL,
        largest REAL NOT NULL,
        rank INTEGER NOT NULL,
        rate REAL NOT NULL,
        cloned_by INTEGER,
        cloned_at INTEGER NOT NULL
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


def save_cloned_stats(user_id: int, values: dict, admin_id: int) -> None:
    _conn.execute(
        "INSERT OR REPLACE INTO cloned_stats (user_id, total, worth, largest, rank, rate, cloned_by, cloned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, values["total"], values["worth"], values["largest"], values["rank"], values["rate"],
         admin_id, int(time.time())),
    )
    _conn.commit()


def _completed_totals() -> tuple[dict[int, list], dict[int, sqlite3.Row]]:
    """user_id -> [count, worth, largest]; cloned stats are the base, plus deals closed after cloning."""
    clones = {r["user_id"]: r for r in _conn.execute("SELECT * FROM cloned_stats")}
    totals = {uid: [c["total"], c["worth"], c["largest"]] for uid, c in clones.items()}
    rows = _conn.execute(
        "SELECT seller_id, buyer_id, amount, closed_at FROM deals WHERE status = 'completed'"
    ).fetchall()
    for row in rows:
        for uid in {row["seller_id"], row["buyer_id"]}:
            if not uid or (uid in clones and (row["closed_at"] or 0) < clones[uid]["cloned_at"]):
                continue
            entry = totals.setdefault(uid, [0, 0.0, 0.0])
            amount = float(row["amount"])
            entry[0] += 1
            entry[1] += amount
            entry[2] = max(entry[2], amount)
    return totals, clones


def user_stats(user_id: int) -> dict:
    """count, total, largest, rank, rate (rate is None unless cloned)."""
    totals, clones = _completed_totals()
    count, worth, largest = totals.get(user_id, [0, 0.0, 0.0])
    clone = clones.get(user_id)
    if clone:
        rank = clone["rank"]
    else:
        rank = 1 + sum(1 for uid, t in totals.items() if uid != user_id and t[1] > worth)
    return {
        "count": count, "total": worth, "largest": largest, "rank": rank,
        "rate": clone["rate"] if clone else None,
    }


def confirmed_deal_for_party(chat_id: int, user_id: int) -> Optional[sqlite3.Row]:
    return _conn.execute(
        "SELECT * FROM deals WHERE chat_id = ? AND status = 'confirmed' AND ? IN (seller_id, buyer_id) "
        "ORDER BY num DESC LIMIT 1",
        (chat_id, user_id),
    ).fetchone()


def track_address(address: str, user_id: int, initial: int) -> int:
    """First sighting starts at `initial`; every later one adds 1. Returns the new count."""
    with _conn:
        _conn.execute(
            "INSERT INTO tracked_addresses (address, count, first_user_id, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(address) DO UPDATE SET count = count + 1, updated_at = excluded.updated_at",
            (address, initial, user_id, int(time.time())),
        )
        row = _conn.execute("SELECT count FROM tracked_addresses WHERE address = ?", (address,)).fetchone()
    return row["count"]


def save_join_notice(user_id: int, chat_id: int, msg_id: int, text: str) -> None:
    _conn.execute(
        "INSERT OR REPLACE INTO join_notices (user_id, chat_id, msg_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, chat_id, msg_id, text, int(time.time())),
    )
    _conn.commit()


def pop_join_notice(user_id: int) -> Optional[sqlite3.Row]:
    with _conn:
        row = _conn.execute("SELECT * FROM join_notices WHERE user_id = ?", (user_id,)).fetchone()
        _conn.execute("DELETE FROM join_notices WHERE user_id = ?", (user_id,))
    return row
