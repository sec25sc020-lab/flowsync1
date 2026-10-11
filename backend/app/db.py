"""SQLite persistence for the prototype simulation."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(os.getenv("FLOWSYNC_DB", Path(__file__).resolve().parents[1] / "flowsync.db"))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS intersections (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                phase_direction TEXT NOT NULL, phase TEXT NOT NULL, remaining_seconds INTEGER NOT NULL,
                next_direction TEXT NOT NULL, phase_started INTEGER NOT NULL DEFAULT 0,
                next_green_seconds INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS roads (
                intersection_id TEXT NOT NULL, direction TEXT NOT NULL, vehicle_count INTEGER NOT NULL,
                queue_length INTEGER NOT NULL, waiting_seconds INTEGER NOT NULL,
                PRIMARY KEY (intersection_id, direction)
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                intersection_id TEXT NOT NULL, total_vehicles INTEGER NOT NULL,
                average_wait INTEGER NOT NULL, total_queue INTEGER NOT NULL,
                congestion TEXT NOT NULL, phase_direction TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS emergencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_type TEXT NOT NULL,
                origin TEXT NOT NULL, destination TEXT NOT NULL, status TEXT NOT NULL,
                eta_seconds INTEGER NOT NULL, created_at TEXT NOT NULL, passed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
                action TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(intersections)")}
        if "next_green_seconds" not in columns:
            db.execute("ALTER TABLE intersections ADD COLUMN next_green_seconds INTEGER NOT NULL DEFAULT 0")
        if db.execute("SELECT COUNT(*) FROM intersections").fetchone()[0] == 0:
            seed(db)


def seed(db: sqlite3.Connection) -> None:
    intersections = [
        ("central-square", "Central Square", "North", "green", 16, "East"),
        ("river-bridge", "River Bridge", "East", "green", 21, "South"),
        ("market-street", "Market Street", "South", "green", 12, "West"),
    ]
    for identifier, name, direction, phase, remaining, next_direction in intersections:
        db.execute(
            "INSERT INTO intersections (id, name, enabled, phase_direction, phase, remaining_seconds, next_direction, phase_started) VALUES (?, ?, 1, ?, ?, ?, ?, 0)",
            (identifier, name, direction, phase, remaining, next_direction),
        )
        base = [4, 10, 16, 8] if identifier == "central-square" else [7, 14, 9, 12] if identifier == "river-bridge" else [12, 5, 18, 6]
        from .engine import DIRECTIONS
        for index, road in enumerate(DIRECTIONS):
            queue = base[index]
            db.execute(
                "INSERT INTO roads VALUES (?, ?, ?, ?, ?)",
                (identifier, road, queue + 3, queue, queue * 4 + index * 5),
            )
    db.execute("INSERT OR REPLACE INTO settings VALUES ('minimum_green', '10')")
    db.execute("INSERT OR REPLACE INTO settings VALUES ('maximum_green', '45')")
    now = utc_now()
    for offset in range(14 * 24 - 1, -1, -1):
        stamp = (now - timedelta(hours=offset)).isoformat()
        for idx, (identifier, _, direction, _, _, _) in enumerate(intersections):
            total = 35 + ((offset * 7 + idx * 11) % 42)
            waiting = 18 + ((offset * 5 + idx * 8) % 40)
            queued = 8 + ((offset * 3 + idx * 6) % 35)
            db.execute(
                "INSERT INTO snapshots (created_at, intersection_id, total_vehicles, average_wait, total_queue, congestion, phase_direction) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (stamp, identifier, total, waiting, queued, "High" if queued > 27 else "Medium", direction),
            )


def log_action(actor: str, action: str, details: dict[str, Any], connection: sqlite3.Connection | None = None) -> None:
    if connection is not None:
        connection.execute(
            "INSERT INTO audit_log (actor, action, details, created_at) VALUES (?, ?, ?, ?)",
            (actor, action, json.dumps(details), utc_now().isoformat()),
        )
        return
    with connect() as db:
        db.execute(
            "INSERT INTO audit_log (actor, action, details, created_at) VALUES (?, ?, ?, ?)",
            (actor, action, json.dumps(details), utc_now().isoformat()),
        )
