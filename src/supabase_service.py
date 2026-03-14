from __future__ import annotations

import os
from typing import Any

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]


def _normalize_plate(plate_number: str) -> str:
    return plate_number.strip().upper().replace(" ", "").replace("-", "")


class SupabaseService:
    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
    ) -> None:
        self.url = (url or os.getenv("SUPABASE_URL", "")).strip()
        self.key = (key or os.getenv("SUPABASE_KEY", "")).strip()
        self._client: Client | None = None

        if self.url and self.key and create_client is not None:
            self._client = create_client(self.url, self.key)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def get_permit_by_plate(self, plate_number: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        normalized_plate = _normalize_plate(plate_number)
        response = (
            self._client.table("permit_holders")
            .select("*")
            .eq("plate_number", normalized_plate)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def upsert_permit_holder(
        self,
        plate_number: str,
        lot_id: str | None,
        expiration: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        payload = {
            "plate_number": _normalize_plate(plate_number),
            "lot_id": lot_id,
            "expiration": expiration,
            "is_active": True,
        }
        response = (
            self._client.table("permit_holders")
            .upsert(payload, on_conflict="plate_number")
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def insert_scan_log(
        self,
        plate_number: str,
        timestamp: str,
        result: str,
        lot_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        payload = {
            "plate_number": _normalize_plate(plate_number),
            "scanned_at": timestamp,
            "result": result,
            "lot_id": lot_id,
        }
        response = self._client.table("scan_logs").insert(payload).execute()
        rows = response.data or []
        return rows[0] if rows else None

    def get_recent_scan_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        response = (
            self._client.table("scan_logs")
            .select("*")
            .order("scanned_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def list_permit_holders(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        response = (
            self._client.table("permit_holders")
            .select("*")
            .order("updated_at", desc=False)
            .execute()
        )
        return response.data or []
