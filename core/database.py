"""V2 数据库层 —— 优化 schema，支持数据过期清理。"""

import json
import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "data.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化 V2 表结构。"""
    with get_conn() as conn:
        conn.executescript("""
            -- ── 原始事件（轻量） ────────────────────
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                type TEXT NOT NULL,
                detail TEXT,
                window TEXT DEFAULT '',
                seq_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

            -- ── 动作序列 ────────────────────────────
            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts TEXT,
                end_ts TEXT,
                window TEXT DEFAULT '',
                app TEXT DEFAULT '',
                action_count INTEGER DEFAULT 0,
                summary TEXT DEFAULT ''
            );

            -- ── 习惯 ────────────────────────────────
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                desc TEXT DEFAULT '',
                pattern_type TEXT DEFAULT 'time',
                confidence REAL DEFAULT 0.0,
                frequency TEXT DEFAULT 'daily',
                typical_time TEXT DEFAULT '',
                window_context TEXT DEFAULT '',
                actions_json TEXT DEFAULT '[]',
                triggers_json TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                is_auto INTEGER DEFAULT 0,
                source TEXT DEFAULT 'auto',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_habits_active ON habits(is_active);

            -- ── 执行记录 ────────────────────────────
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
                ts TEXT DEFAULT (datetime('now','localtime')),
                success INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                triggered_by TEXT DEFAULT 'manual',
                note TEXT DEFAULT ''
            );

            -- ── 每日统计 ────────────────────────────
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                clicks INTEGER DEFAULT 0,
                keys INTEGER DEFAULT 0,
                app_usage TEXT DEFAULT '{}',
                habits_new INTEGER DEFAULT 0,
                habits_run INTEGER DEFAULT 0,
                active_minutes INTEGER DEFAULT 0
            );
        """)


# ═══════════════════════════════════════════════
# 事件
# ═══════════════════════════════════════════════

def insert_event(type_: str, detail: dict, window: str = "", seq_id: int = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO events (type, detail, window, seq_id) VALUES (?, ?, ?, ?)",
            (type_, json.dumps(detail, ensure_ascii=False), window, seq_id)
        )
        return cur.lastrowid


def get_events_since(since: str, limit: int = 1000) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE ts > ? ORDER BY ts LIMIT ?", (since, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_today_events() -> list:
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE ts >= ? ORDER BY ts", (today,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_event_count_since(since: str) -> dict:
    """返回各类型事件计数。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM events WHERE ts > ? GROUP BY type",
            (since,)
        ).fetchall()
        return {r["type"]: r["cnt"] for r in rows}


# ═══════════════════════════════════════════════
# 序列
# ═══════════════════════════════════════════════

def create_sequence(start_ts: str, window: str = "", app: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sequences (start_ts, window, app) VALUES (?, ?, ?)",
            (start_ts, window, app)
        )
        return cur.lastrowid


def update_sequence(seq_id: int, end_ts: str, count: int, summary: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sequences SET end_ts=?, action_count=?, summary=? WHERE id=?",
            (end_ts, count, summary, seq_id)
        )


def get_recent_sequences(days: int = 7) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sequences WHERE start_ts > datetime('now','localtime',?) "
            "ORDER BY start_ts DESC", (f'-{days} days',)
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════
# 习惯
# ═══════════════════════════════════════════════

def save_habit(name: str, desc: str, pattern_type: str, confidence: float,
               frequency: str, typical_time: str, window_context: str,
               actions_json: str, triggers: dict = None,
               is_auto: bool = False, source: str = "auto") -> int:
    # 去重合并
    existing = _find_similar(typical_time, window_context, pattern_type)
    if existing:
        _update_habit(existing["id"],
                      name=name, desc=desc, confidence=confidence,
                      frequency=frequency, actions_json=actions_json,
                      is_auto=is_auto)
        return existing["id"]

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO habits (name, desc, pattern_type, confidence, frequency,
               typical_time, window_context, actions_json, triggers_json, is_auto, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (name, desc, pattern_type, confidence, frequency,
             typical_time, window_context, actions_json,
             json.dumps(triggers or {}, ensure_ascii=False),
             1 if is_auto else 0, source)
        )
        return cur.lastrowid


def _find_similar(typical_time: str, window_context: str, pattern_type: str) -> Optional[dict]:
    if not typical_time and not window_context:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM habits WHERE is_active=1
               AND typical_time LIKE ? AND window_context=?
               AND pattern_type=? LIMIT 1""",
            (f"{typical_time[:5]}%" if typical_time else "%",
             window_context, pattern_type)
        ).fetchone()
        return dict(row) if row else None


def _update_habit(hid: int, **kw):
    kw["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [hid]
    with get_conn() as conn:
        conn.execute(f"UPDATE habits SET {set_clause} WHERE id=?", vals)


def get_habits(active_only: bool = True) -> list:
    q = "SELECT * FROM habits"
    p = []
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY confidence DESC, typical_time"
    with get_conn() as conn:
        rows = conn.execute(q, p).fetchall()
        return [dict(r) for r in rows]


def search_habits(keyword: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM habits WHERE is_active=1 AND (name LIKE ? OR desc LIKE ? OR window_context LIKE ?)",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        ).fetchall()
        return [dict(r) for r in rows]


def get_habit(hid: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM habits WHERE id=?", (hid,)).fetchone()
        return dict(row) if row else None


def delete_habit(hid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM habits WHERE id=?", (hid,))


def toggle_habit(hid: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE habits SET is_active=?, updated_at=datetime('now','localtime') WHERE id=?",
                     (1 if active else 0, hid))


def export_habits() -> list:
    """导出所有习惯为可移植 JSON。"""
    habits = get_habits(active_only=False)
    export = []
    for h in habits:
        export.append({
            "name": h["name"], "desc": h["desc"],
            "pattern_type": h["pattern_type"],
            "actions": json.loads(h["actions_json"] or "[]"),
            "triggers": json.loads(h["triggers_json"] or "{}"),
            "is_auto": bool(h["is_auto"]),
        })
    return export


def import_habits(data: list) -> int:
    """从 JSON 导入习惯，返回导入数量。"""
    count = 0
    for item in data:
        try:
            save_habit(
                name=item.get("name", "导入的习惯"),
                desc=item.get("desc", ""),
                pattern_type=item.get("pattern_type", "sequence"),
                confidence=0.5,
                frequency="daily",
                typical_time="",
                window_context="",
                actions_json=json.dumps(item.get("actions", []), ensure_ascii=False),
                triggers=item.get("triggers", {}),
                source="import",
            )
            count += 1
        except Exception as e:
            print(f"[导入] 跳过: {e}")
    return count


# ═══════════════════════════════════════════════
# 执行记录
# ═══════════════════════════════════════════════

def log_exec(habit_id: int, success: bool, duration_ms: int,
             triggered_by: str = "manual", note: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO executions (habit_id, success, duration_ms, triggered_by, note) VALUES (?,?,?,?,?)",
            (habit_id, 1 if success else 0, duration_ms, triggered_by, note)
        )


def get_exec_stats(habit_id: int) -> dict:
    with get_conn() as conn:
        t = conn.execute("SELECT COUNT(*) as c FROM executions WHERE habit_id=?",
                         (habit_id,)).fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) as c FROM executions WHERE habit_id=? AND success=1",
                         (habit_id,)).fetchone()["c"]
        return {"total": t, "success": s, "fail": t - s}


def get_exec_history(habit_id: int, limit: int = 20) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM executions WHERE habit_id=? ORDER BY ts DESC LIMIT ?",
            (habit_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════
# 每日统计 & 清理
# ═══════════════════════════════════════════════

def update_daily_stats(today: str = None):
    today = today or date.today().isoformat()
    with get_conn() as conn:
        counts = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM events WHERE date(ts)=? GROUP BY type",
            (today,)
        ).fetchall()
        cnt_map = {r["type"]: r["cnt"] for r in counts}

        app_rows = conn.execute(
            "SELECT window, COUNT(*) as cnt FROM events WHERE date(ts)=? AND window!='' GROUP BY window ORDER BY cnt DESC",
            (today,)
        ).fetchall()
        app_usage = {r["window"]: r["cnt"] for r in app_rows if r["window"]}

        conn.execute("""
            INSERT INTO daily_stats (date, clicks, keys, app_usage)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
            clicks=excluded.clicks, keys=excluded.keys, app_usage=excluded.app_usage
        """, (today, cnt_map.get("click", 0), cnt_map.get("keypress", 0),
              json.dumps(app_usage, ensure_ascii=False)))


def get_daily_stats(days: int = 30) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]


def clean_old_data(retention_days: int = 30):
    """清理过期数据。"""
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()
    with get_conn() as conn:
        for table in ("events", "sequences"):
            conn.execute(f"DELETE FROM {table} WHERE date(ts) < ?", (cutoff,))
