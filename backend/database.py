"""
SQLite persistence for VoltStream app data (dashboard, devices, billing, analytics, chat).
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "volttream.db")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS dashboard_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                grid_power REAL NOT NULL,
                solar_generation REAL NOT NULL,
                net_consumption REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_summary (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_bill REAL NOT NULL,
                projected_bill REAL NOT NULL,
                budget_alert TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                amount REAL NOT NULL,
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT NOT NULL UNIQUE,
                date_label TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analytics_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_name TEXT NOT NULL,
                usage_kwh REAL NOT NULL,
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                budget_goal REAL NOT NULL,
                primary_goal TEXT NOT NULL,
                household_size INTEGER NOT NULL,
                daily_schedule TEXT NOT NULL
            );
            """
        )

    _seed_if_empty()
    _ensure_washing_machine_device()
    _ensure_user_profile()


def _ensure_user_profile() -> None:
    """Ensure a user profile row exists in the user_profile table."""
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM user_profile").fetchone()["c"]
        if n == 0:
            conn.execute(
                """INSERT INTO user_profile (id, name, budget_goal, primary_goal, household_size, daily_schedule)
                   VALUES (1, 'User', 150.0, 'savings', 3, 'work-from-home')"""
            )


def _ensure_washing_machine_device() -> None:
    """Ensure a Washing Machine row exists (for DBs seeded before it was added)."""
    with get_connection() as conn:
        n = conn.execute(
            """SELECT COUNT(*) AS c FROM devices
               WHERE instr(lower(name), 'washing') > 0 OR instr(lower(name), 'washer') > 0"""
        ).fetchone()["c"]
        if n == 0:
            conn.execute(
                "INSERT INTO devices (name, status) VALUES (?, ?)",
                ("Washing Machine", 1),
            )


def _seed_if_empty() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM devices")
        if cur.fetchone()["c"] > 0:
            return

        now = _utc_now_iso()
        cur.execute(
            """INSERT OR REPLACE INTO dashboard_metrics
               (id, grid_power, solar_generation, net_consumption, updated_at)
               VALUES (1, 4.2, 8.5, 2.1, ?)""",
            (now,),
        )

        for name, status in [
            ("Living Room Lights", True),
            ("Kitchen TV", False),
            ("Master Bedroom AC", True),
            ("Garage Door", True),
            ("Washing Machine", True),
        ]:
            cur.execute(
                "INSERT INTO devices (name, status) VALUES (?, ?)",
                (name, 1 if status else 0),
            )

        cur.execute(
            """INSERT OR REPLACE INTO billing_summary
               (id, current_bill, projected_bill, budget_alert)
               VALUES (1, 1800, 1950, 'You are at 78% of your monthly energy budget.')"""
        )

        history = [
            ("Jan", 1200, 1),
            ("Feb", 1100, 2),
            ("Mar", 1400, 3),
            ("Apr", 1350, 4),
            ("May", 1800, 5),
            ("Jun", 1600, 6),
        ]
        for month, amount, order in history:
            cur.execute(
                "INSERT INTO billing_history (month, amount, sort_order) VALUES (?, ?, ?)",
                (month, amount, order),
            )

        transactions = [
            ("INV-2026-05", "May 01, 2026", 1800, "Pending"),
            ("INV-2026-04", "Apr 01, 2026", 1350, "Paid"),
            ("INV-2026-03", "Mar 01, 2026", 1400, "Paid"),
            ("INV-2026-02", "Feb 01, 2026", 1100, "Paid"),
            ("INV-2026-01", "Jan 01, 2026", 1200, "Paid"),
            ("INV-2025-12", "Dec 01, 2025", 1550, "Paid"),
        ]
        for inv, dlabel, amt, st in transactions:
            cur.execute(
                """INSERT INTO billing_transactions (invoice_id, date_label, amount, status)
                   VALUES (?, ?, ?, ?)""",
                (inv, dlabel, amt, st),
            )

        daily = [
            ("Mon", 12.4, 1),
            ("Tue", 15.1, 2),
            ("Wed", 11.8, 3),
            ("Thu", 14.2, 4),
            ("Fri", 18.6, 5),
            ("Sat", 16.3, 6),
            ("Sun", 13.0, 7),
        ]
        for day, usage, order in daily:
            cur.execute(
                "INSERT INTO analytics_daily (day_name, usage_kwh, sort_order) VALUES (?, ?, ?)",
                (day, usage, order),
            )


def get_dashboard() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM dashboard_metrics WHERE id = 1").fetchone()
        if not row:
            return {"grid_power": 0, "solar_generation": 0, "net_consumption": 0}
        return {
            "grid_power": row["grid_power"],
            "solar_generation": row["solar_generation"],
            "net_consumption": row["net_consumption"],
        }


def list_devices() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, status FROM devices ORDER BY id"
        ).fetchall()
        return [
            {"id": r["id"], "name": r["name"], "status": bool(r["status"])}
            for r in rows
        ]


def update_device_status(device_id: int, status: bool) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE devices SET status = ? WHERE id = ?",
            (1 if status else 0, device_id),
        )
        return cur.rowcount > 0


def save_chat_messages(user_text: str, assistant_text: str) -> None:
    now = _utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)",
            ("user", user_text, now),
        )
        conn.execute(
            "INSERT INTO chat_messages (role, content, created_at) VALUES (?, ?, ?)",
            ("assistant", assistant_text, now),
        )


def get_chat_history(limit: int = 200) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT role, content FROM chat_messages
               ORDER BY id ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def clear_chat_history() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages")


def get_billing_summary() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM billing_summary WHERE id = 1").fetchone()
        if not row:
            return {
                "current_bill": 0,
                "projected_bill": 0,
                "budget_alert": "",
            }
        return {
            "current_bill": row["current_bill"],
            "projected_bill": row["projected_bill"],
            "budget_alert": row["budget_alert"],
        }


def list_billing_history() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT month, amount FROM billing_history ORDER BY sort_order ASC"
        ).fetchall()
        return [{"month": r["month"], "amount": r["amount"]} for r in rows]


def list_billing_transactions() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT invoice_id AS id, date_label AS date, amount, status
               FROM billing_transactions ORDER BY id DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_analytics_daily() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT day_name AS day, usage_kwh AS usage FROM analytics_daily ORDER BY sort_order ASC"
        ).fetchall()
        return [{"day": r["day"], "usage": r["usage"]} for r in rows]


def get_user_profile() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
        if not row:
            return {
                "name": "User",
                "budget_goal": 150.0,
                "primary_goal": "savings",
                "household_size": 3,
                "daily_schedule": "work-from-home",
            }
        return {
            "name": row["name"],
            "budget_goal": row["budget_goal"],
            "primary_goal": row["primary_goal"],
            "household_size": row["household_size"],
            "daily_schedule": row["daily_schedule"],
        }


def update_user_profile(profile: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            """UPDATE user_profile
               SET name = ?, budget_goal = ?, primary_goal = ?, household_size = ?, daily_schedule = ?
               WHERE id = 1""",
            (
                profile.get("name", "User"),
                float(profile.get("budget_goal", 150.0)),
                profile.get("primary_goal", "savings"),
                int(profile.get("household_size", 3)),
                profile.get("daily_schedule", "work-from-home"),
            ),
        )
    return get_user_profile()
