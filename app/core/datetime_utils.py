from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def format_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Formats a datetime object as a full ISO-8601 string with UTC 'Z' suffix.
    E.g. '2026-10-22T10:41:25.123456Z'.
    """
    if dt is None:
        return None

    # Attach UTC timezone if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    elif not iso.endswith("Z"):
        return iso + "Z"
    return iso
