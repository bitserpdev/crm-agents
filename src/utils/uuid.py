import uuid as _uuid


def new_id() -> str:
    """New UUID4 string — use everywhere instead of str(uuid.uuid4())."""
    return str(_uuid.uuid4())


def new_trace_id() -> str:
    """Alias for agent trace IDs — same as new_id() but signals intent."""
    return str(_uuid.uuid4())


def is_valid(value: str) -> bool:
    """Check if a string is a valid UUID — used in qdrant point ID safety."""
    try:
        _uuid.UUID(str(value))
        return True
    except ValueError:
        return False