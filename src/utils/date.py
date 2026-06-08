from datetime import datetime, timezone


def today_str() -> str:
    """'2024-01-15' — used for digest dedup keys, log filenames."""
    return datetime.now().strftime("%Y-%m-%d")


def now_display_str() -> str:
    """'January 15, 2024' — used in email templates."""
    return datetime.now().strftime("%B %d, %Y")


def now_year_str() -> str:
    """'2024' — used in email footer copyright."""
    return str(datetime.now().year)


def now_iso() -> str:
    """'2024-01-15T10:30:00+00:00' — used for received_at fields."""
    return datetime.now(timezone.utc).isoformat()


def is_today(value: str) -> bool:
    """
    Check if a date string matches today.
    Used in digest dedup: is_today(r.get('op:digest:last_run'))
    """
    if not value:
        return False
    if isinstance(value, bytes):
        value = value.decode()
    return value == today_str()