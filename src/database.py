import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def _normalize_plate(plate):
    """Normalize plate strings for consistent matching/storage."""
    if not plate:
        return plate
    return plate.strip().upper().replace(" ", "").replace("-", "")


class VehicleDatabase:

    def __init__(self, db_path="data/database.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                plate       TEXT,
                track_id    INTEGER,
                space       TEXT,
                entry_time  TEXT,
                exit_time   TEXT,
                duration    REAL
            );
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT UNIQUE NOT NULL,
                owner_name TEXT
            );
            CREATE TABLE IF NOT EXISTS permits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                permit_type TEXT,
                expiration_date TEXT,
                is_active INTEGER
            );
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT,
                timestamp TEXT,
                reason TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                result TEXT NOT NULL,
                lot_id TEXT,
                synced_to_cloud INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self._ensure_column_exists("permits", "lot_id", "TEXT")
        self._ensure_column_exists("permits", "updated_at", "TEXT")
        self._ensure_column_exists("scan_logs", "lot_id", "TEXT")
        self._ensure_column_exists(
            "scan_logs",
            "synced_to_cloud",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self.conn.commit()

    def _ensure_column_exists(self, table_name, column_name, column_type_sql):
        columns = {
            row[1]
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        self.conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_sql}"
        )

    # --- Session tracking ---

    def log_exit(self, track_id, plate, space, entry_time, exit_time):
        plate = _normalize_plate(plate)
        duration = exit_time - entry_time if entry_time and exit_time else None
        entry_iso = (
            datetime.fromtimestamp(entry_time).isoformat(timespec="seconds")
            if entry_time
            else None
        )
        exit_iso = (
            datetime.fromtimestamp(exit_time).isoformat(timespec="seconds")
            if exit_time
            else None
        )
        try:
            self.conn.execute(
                """INSERT INTO sessions (plate, track_id, space, entry_time, exit_time, duration)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plate, track_id, space, entry_iso, exit_iso, duration),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to log exit for track %s: %s", track_id, e)

    def get_sessions(self, plate=None, limit=100):
        if plate:
            plate = _normalize_plate(plate)
            rows = self.conn.execute(
                "SELECT * FROM sessions WHERE plate=? ORDER BY entry_time DESC LIMIT ?",
                (plate, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM sessions ORDER BY entry_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows

    # --- Vehicle registry ---

    def add_vehicle(self, license_plate, owner_name=None):
        license_plate = _normalize_plate(license_plate)
        try:
            self.conn.execute(
                """INSERT INTO vehicles (license_plate, owner_name)
                   VALUES (?, ?)
                   ON CONFLICT(license_plate) DO UPDATE SET owner_name = excluded.owner_name""",
                (license_plate, owner_name),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to add vehicle %s: %s", license_plate, e)

    # --- Permits ---

    def add_permit(
        self,
        license_plate,
        permit_type,
        expiration_date,
        lot_id=None,
        is_active=True,
        updated_at=None,
    ):
        """Add an active permit. expiration_date: YYYY-MM-DD."""
        license_plate = _normalize_plate(license_plate)
        updated_at = updated_at or datetime.now().isoformat(timespec="seconds")
        try:
            self.conn.execute(
                """INSERT INTO permits (
                       license_plate, lot_id, permit_type, expiration_date, is_active, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    license_plate,
                    lot_id,
                    permit_type,
                    expiration_date,
                    int(is_active),
                    updated_at,
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to add permit for %s: %s", license_plate, e)

    def upsert_permit_record(
        self,
        license_plate,
        lot_id,
        expiration_date,
        permit_type="supabase",
        is_active=True,
        updated_at=None,
    ):
        license_plate = _normalize_plate(license_plate)
        updated_at = updated_at or datetime.now().isoformat(timespec="seconds")
        try:
            self.conn.execute(
                "DELETE FROM permits WHERE license_plate = ?",
                (license_plate,),
            )
            self.conn.execute(
                """INSERT INTO permits (
                       license_plate, lot_id, permit_type, expiration_date, is_active, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    license_plate,
                    lot_id,
                    permit_type,
                    expiration_date,
                    int(is_active),
                    updated_at,
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to upsert permit for %s: %s", license_plate, e)

    def check_permit(self, license_plate):
        """Return True if the plate has an active, non-expired permit."""
        license_plate = _normalize_plate(license_plate)
        today_iso = date.today().isoformat()
        row = self.conn.execute(
            """SELECT 1 FROM permits
               WHERE license_plate = ? AND is_active = 1 AND expiration_date >= ?
               LIMIT 1""",
            (license_plate, today_iso),
        ).fetchone()
        return row is not None

    def get_active_permit(self, license_plate):
        """Return active permit details dict, or None."""
        license_plate = _normalize_plate(license_plate)
        today_iso = date.today().isoformat()
        row = self.conn.execute(
            """SELECT lot_id, permit_type, expiration_date FROM permits
               WHERE license_plate = ? AND is_active = 1 AND expiration_date >= ?
               ORDER BY expiration_date DESC LIMIT 1""",
            (license_plate, today_iso),
        ).fetchone()
        if row is None:
            return None
        return {"lot_id": row[0], "permit_type": row[1], "expiration_date": row[2]}

    def list_permits(self):
        rows = self.conn.execute(
            """SELECT license_plate, lot_id, permit_type, expiration_date, is_active, updated_at
               FROM permits
               ORDER BY license_plate"""
        ).fetchall()
        return [
            {
                "license_plate": row[0],
                "lot_id": row[1],
                "permit_type": row[2],
                "expiration_date": row[3],
                "is_active": bool(row[4]),
                "updated_at": row[5],
            }
            for row in rows
        ]

    def sync_permits_from_cloud(self, permit_rows):
        synced_count = 0
        for row in permit_rows:
            plate_number = row.get("plate_number") or row.get("license_plate")
            expiration = row.get("expiration") or row.get("expiration_date")
            if not plate_number or not expiration:
                continue
            self.upsert_permit_record(
                license_plate=plate_number,
                lot_id=row.get("lot_id"),
                expiration_date=expiration,
                permit_type=row.get("permit_type") or "supabase",
                is_active=bool(row.get("is_active", True)),
                updated_at=row.get("updated_at"),
            )
            synced_count += 1
        return synced_count

    def deactivate_permits(self, license_plate):
        """Set is_active = 0 for all permits for the given plate."""
        license_plate = _normalize_plate(license_plate)
        try:
            self.conn.execute(
                "UPDATE permits SET is_active = 0 WHERE license_plate = ?",
                (license_plate,),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to deactivate permits for %s: %s", license_plate, e)

    # --- Violations ---

    def record_violation(self, license_plate, reason):
        """Insert a violation with current timestamp."""
        license_plate = _normalize_plate(license_plate)
        timestamp_iso = datetime.now().isoformat(timespec="seconds")
        try:
            self.conn.execute(
                """INSERT INTO violations (license_plate, timestamp, reason)
                   VALUES (?, ?, ?)""",
                (license_plate, timestamp_iso, reason),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to record violation for %s: %s", license_plate, e)

    # --- Scan logs ---

    def record_scan_log(
        self,
        license_plate,
        timestamp_iso,
        result,
        lot_id=None,
        synced_to_cloud=False,
    ):
        license_plate = _normalize_plate(license_plate)
        try:
            cursor = self.conn.execute(
                """INSERT INTO scan_logs (license_plate, timestamp, result, lot_id, synced_to_cloud)
                   VALUES (?, ?, ?, ?, ?)""",
                (license_plate, timestamp_iso, result, lot_id, int(synced_to_cloud)),
            )
            self.conn.commit()
            return int(cursor.lastrowid)
        except sqlite3.Error as e:
            log.error("Failed to record scan log for %s: %s", license_plate, e)
            return None

    def mark_scan_log_synced(self, scan_log_id):
        try:
            self.conn.execute(
                "UPDATE scan_logs SET synced_to_cloud = 1 WHERE id = ?",
                (scan_log_id,),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to mark scan log %s as synced: %s", scan_log_id, e)

    def get_recent_scan_logs(self, limit=20):
        rows = self.conn.execute(
            """SELECT id, license_plate, timestamp, result, lot_id, synced_to_cloud
               FROM scan_logs
               ORDER BY timestamp DESC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
        return [
            {
                "id": row[0],
                "license_plate": row[1],
                "timestamp": row[2],
                "result": row[3],
                "lot_id": row[4],
                "synced_to_cloud": bool(row[5]),
            }
            for row in rows
        ]

    def get_unsynced_scan_logs(self, limit=100):
        rows = self.conn.execute(
            """SELECT id, license_plate, timestamp, result, lot_id, synced_to_cloud
               FROM scan_logs
               WHERE synced_to_cloud = 0
               ORDER BY timestamp ASC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
        return [
            {
                "id": row[0],
                "license_plate": row[1],
                "timestamp": row[2],
                "result": row[3],
                "lot_id": row[4],
                "synced_to_cloud": bool(row[5]),
            }
            for row in rows
        ]

    def close(self):
        self.conn.close()


_db = None


def _get_db():
    global _db
    if _db is None:
        _db = VehicleDatabase()
    return _db


def init_database():
    _get_db()


def add_vehicle(license_plate, owner_name=None):
    _get_db().add_vehicle(license_plate, owner_name)


def add_permit(
    license_plate,
    permit_type,
    expiration_date,
    lot_id=None,
    is_active=True,
    updated_at=None,
):
    _get_db().add_permit(
        license_plate,
        permit_type,
        expiration_date,
        lot_id=lot_id,
        is_active=is_active,
        updated_at=updated_at,
    )


def upsert_permit_record(
    license_plate,
    lot_id,
    expiration_date,
    permit_type="supabase",
    is_active=True,
    updated_at=None,
):
    _get_db().upsert_permit_record(
        license_plate,
        lot_id,
        expiration_date,
        permit_type=permit_type,
        is_active=is_active,
        updated_at=updated_at,
    )


def check_permit(license_plate):
    return _get_db().check_permit(license_plate)


def get_active_permit(license_plate):
    return _get_db().get_active_permit(license_plate)


def list_permits():
    return _get_db().list_permits()


def sync_permits_from_cloud(permit_rows):
    return _get_db().sync_permits_from_cloud(permit_rows)


def deactivate_permits(license_plate):
    _get_db().deactivate_permits(license_plate)


def record_violation(license_plate, reason):
    _get_db().record_violation(license_plate, reason)


def record_scan_log(
    license_plate,
    timestamp_iso,
    result,
    lot_id=None,
    synced_to_cloud=False,
):
    return _get_db().record_scan_log(
        license_plate,
        timestamp_iso,
        result,
        lot_id=lot_id,
        synced_to_cloud=synced_to_cloud,
    )


def mark_scan_log_synced(scan_log_id):
    _get_db().mark_scan_log_synced(scan_log_id)


def get_recent_scan_logs(limit=20):
    return _get_db().get_recent_scan_logs(limit=limit)


def get_unsynced_scan_logs(limit=100):
    return _get_db().get_unsynced_scan_logs(limit=limit)
