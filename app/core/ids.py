"""UUID helpers. All public IDs are uuid4 hex."""
import uuid


def new_id() -> str:
    return uuid.uuid4().hex


def is_id(value: str) -> bool:
    try:
        uuid.UUID(hex=value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
