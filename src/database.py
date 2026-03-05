"""SQLite database layer for parking lot permit checks.

This module keeps all database access in one place so other modules can do:
    from src.database import check_permit
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "parking.db"


def _get_connection() -> sqlite3.Connection:
    """Create a new SQLite connection."""
    return sqlite3.connect(DB_PATH)


def _normalize_plate(plate: str) -> str:
    """Normalize plate strings for consistent matching/storage."""
    return plate.strip().upper().replace(" ", "").replace("-", "")


def init_database() -> None:
    """Create the database and required tables if they do not already exist."""
    with closing(_get_connection()) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_plate TEXT UNIQUE NOT NULL,
                    owner_name TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS permits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_plate TEXT,
                    permit_type TEXT,
                    expiration_date TEXT,
                    is_active INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_plate TEXT,
                    timestamp TEXT,
                    reason TEXT
                )
                """
            )


def add_vehicle(license_plate: str, owner_name: str | None = None) -> None:
    """Insert or update a vehicle record by license plate."""
    license_plate = _normalize_plate(license_plate)
    init_database()
    with closing(_get_connection()) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO vehicles (license_plate, owner_name)
                VALUES (?, ?)
                ON CONFLICT(license_plate) DO UPDATE SET owner_name = excluded.owner_name
                """,
                (license_plate, owner_name),
            )


def add_permit(license_plate: str, permit_type: str, expiration_date: str) -> None:
    """Add an active permit for a plate.

    expiration_date must be ISO format: YYYY-MM-DD.
    """
    license_plate = _normalize_plate(license_plate)
    init_database()
    with closing(_get_connection()) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO permits (license_plate, permit_type, expiration_date, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (license_plate, permit_type, expiration_date),
            )


def check_permit(license_plate: str) -> bool:
    """Return True if the plate has an active and non-expired permit."""
    license_plate = _normalize_plate(license_plate)
    init_database()
    today_iso = date.today().isoformat()
    with closing(_get_connection()) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM permits
            WHERE license_plate = ?
              AND is_active = 1
              AND expiration_date >= ?
            LIMIT 1
            """,
            (license_plate, today_iso),
        ).fetchone()
    return row is not None


def get_active_permit(license_plate: str) -> dict | None:
    """Return active non-expired permit details, or None."""
    license_plate = _normalize_plate(license_plate)
    init_database()
    today_iso = date.today().isoformat()
    with closing(_get_connection()) as conn:
        row = conn.execute(
            """
            SELECT permit_type, expiration_date
            FROM permits
            WHERE license_plate = ?
              AND is_active = 1
              AND expiration_date >= ?
            ORDER BY expiration_date DESC
            LIMIT 1
            """,
            (license_plate, today_iso),
        ).fetchone()
    if row is None:
        return None
    return {"permit_type": row[0], "expiration_date": row[1]}


def deactivate_permits(license_plate: str) -> None:
    """Set is_active = 0 for all permits for the given plate."""
    license_plate = _normalize_plate(license_plate)
    init_database()
    with closing(_get_connection()) as conn:
        with conn:
            conn.execute(
                """
                UPDATE permits
                SET is_active = 0
                WHERE license_plate = ?
                """,
                (license_plate,),
            )


def record_violation(license_plate: str, reason: str) -> None:
    """Insert a violation entry with current ISO timestamp."""
    license_plate = _normalize_plate(license_plate)
    init_database()
    timestamp_iso = datetime.now().isoformat(timespec="seconds")
    with closing(_get_connection()) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO violations (license_plate, timestamp, reason)
                VALUES (?, ?, ?)
                """,
                (license_plate, timestamp_iso, reason),
            )


# Simple example for match.py or plateDetector.py:
# from src.database import check_permit, record_violation
#
# plate_text = "ABC123"
# if check_permit(plate_text):
#     print("Permit valid")
# else:
#     record_violation(plate_text, "No valid parking permit")


if __name__ == "__main__":
    init_database()
    demo_plate = "abc-123"
    add_vehicle(demo_plate, "Demo Owner")
    add_permit(demo_plate, "demo", "2099-12-31")
    print(f"check_permit({demo_plate!r}) -> {check_permit(demo_plate)}")
