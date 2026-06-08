import hashlib
import json


def make_dedup_key(identifier: str) -> str:
    """
    SHA-256 hash of a string identifier.
    Used by all connectors for dedup_key generation.

    Usage:
        make_dedup_key("https://linkedin.com/in/someone")
        make_dedup_key("upwork-job-~01234567890")
    """
    return hashlib.sha256(identifier.encode()).hexdigest()


def make_dedup_key_from_dict(record: dict, fields: list[str]) -> str:
    """
    Build a dedup key from specific fields of a record.
    Useful when no single URL or ID is available.

    Usage:
        make_dedup_key_from_dict(record, ["email", "platform"])
        make_dedup_key_from_dict(record, ["url"])
    """
    parts = {k: record.get(k, "") for k in fields}
    canonical = json.dumps(parts, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def short_hash(identifier: str, length: int = 8) -> str:
    """
    Short hash for display purposes — not for dedup.
    Used in log messages: short_hash(event_id) → '3f2a1b9c'
    """
    return hashlib.sha256(identifier.encode()).hexdigest()[:length]