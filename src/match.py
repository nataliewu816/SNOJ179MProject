"""Plate-to-permit matching helpers."""

from __future__ import annotations

import os

try:
    from src.database import check_permit, record_violation
except ImportError:
    from database import check_permit, record_violation

try:
    from src.supabase_client import (
        supabase_record_event,
        supabase_record_violation,
    )
except ImportError:
    try:
        from supabase_client import supabase_record_event, supabase_record_violation
    except ImportError:
        supabase_record_event = None
        supabase_record_violation = None


def _should_use_supabase() -> bool:
    """Return True when Supabase mirroring is explicitly enabled."""
    return os.getenv("USE_SUPABASE") == "1"


def process_detected_plate(plate_text: str) -> dict:
    """Check whether a detected plate is authorized and record violations."""
    normalized = plate_text.strip().upper()

    if check_permit(normalized):
        if _should_use_supabase() and supabase_record_event is not None:
            supabase_record_event(normalized, "AUTHORIZED")
        return {"plate": normalized, "status": "AUTHORIZED"}

    record_violation(normalized, "No valid permit")
    if _should_use_supabase():
        if supabase_record_violation is not None:
            supabase_record_violation(normalized, "No valid permit")
        if supabase_record_event is not None:
            supabase_record_event(normalized, "UNAUTHORIZED")
    return {"plate": normalized, "status": "UNAUTHORIZED"}


if __name__ == "__main__":
    print(process_detected_plate("abc 123"))
