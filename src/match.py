"""Plate-to-permit matching helpers."""

from __future__ import annotations

try:
    from src.database import check_permit, record_violation
except ImportError:
    from database import check_permit, record_violation


def process_detected_plate(plate_text: str) -> dict:
    """Check whether a detected plate is authorized and record violations."""
    normalized = plate_text.strip().upper()

    if check_permit(normalized):
        return {"plate": normalized, "status": "AUTHORIZED"}

    record_violation(normalized, "No valid permit")
    return {"plate": normalized, "status": "UNAUTHORIZED"}


if __name__ == "__main__":
    print(process_detected_plate("abc 123"))
