"""SQLite 数据库操作层"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "memos.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content     TEXT    NOT NULL,
                category    TEXT    NOT NULL DEFAULT 'other',
                confidence  INTEGER NOT NULL DEFAULT 0,
                tags        TEXT    NOT NULL DEFAULT '[]',
                priority    TEXT    NOT NULL DEFAULT 'medium',
                scheduled_at TEXT,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                memo_id     INTEGER REFERENCES memos(id) ON DELETE CASCADE,
                date        TEXT    NOT NULL,
                time_slot   TEXT,
                title       TEXT    NOT NULL,
                description TEXT,
                priority    TEXT    NOT NULL DEFAULT 'medium',
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memos_category    ON memos(category);
            CREATE INDEX IF NOT EXISTS idx_memos_created_at  ON memos(created_at);
            CREATE INDEX IF NOT EXISTS idx_schedules_date    ON schedules(date);
        """)


# ── Memo CRUD ──────────────────────────────────────────────────────────────

def add_memo(content: str, category: str, confidence: int,
             tags: list, priority: str, scheduled_at: str | None) -> dict:
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO memos (content, category, confidence, tags, priority,
               scheduled_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (content, category, confidence, json.dumps(tags, ensure_ascii=False),
             priority, scheduled_at, now, now)
        )
        return get_memo(cur.lastrowid, conn)


def get_memo(memo_id: int, conn=None) -> dict | None:
    c = conn or get_conn()
    row = c.execute("SELECT * FROM memos WHERE id = ?", (memo_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_memos(category: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        if category and category != "all":
            rows = conn.execute(
                "SELECT * FROM memos WHERE category = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (category, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memos ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_memos(query: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM memos WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_memo(memo_id: int, **fields) -> dict | None:
    allowed = {"content", "category", "confidence", "tags", "priority", "scheduled_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_memo(memo_id)
    if "tags" in updates:
        updates["tags"] = json.dumps(updates["tags"], ensure_ascii=False)
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [memo_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE memos SET {set_clause} WHERE id = ?", values)
        return get_memo(memo_id, conn)


def delete_memo(memo_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM memos WHERE id = ?", (memo_id,))
        return cur.rowcount > 0


# ── Schedule CRUD ──────────────────────────────────────────────────────────

def add_schedule(memo_id: int | None, date: str, time_slot: str | None,
                 title: str, description: str | None, priority: str) -> dict:
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO schedules (memo_id, date, time_slot, title, description, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (memo_id, date, time_slot, title, description, priority, now)
        )
        row = conn.execute("SELECT * FROM schedules WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def get_schedules(date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE date = ? ORDER BY time_slot ASC",
            (date,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM memos").fetchone()[0]
        by_cat = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM memos GROUP BY category"
        ).fetchall()
        today = datetime.now().date().isoformat()
        today_schedules = conn.execute(
            "SELECT COUNT(*) FROM schedules WHERE date = ?", (today,)
        ).fetchone()[0]
    return {
        "total": total,
        "by_category": {r["category"]: r["cnt"] for r in by_cat},
        "today_schedules": today_schedules,
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["tags"] = json.loads(d.get("tags", "[]"))
    except Exception:
        d["tags"] = []
    return d
