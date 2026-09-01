"""Single source of truth for time handling. Nothing else calls datetime.now()."""

from datetime import UTC, datetime


def utcnow_ts() -> int:
    """Return the current UTC time as a Unix epoch integer."""
    return int(datetime.now(UTC).timestamp())


def format_duration(seconds: int) -> str:
    """Render a duration as a compact `2h 15m` style string."""
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
