"""Single source of truth for "now" — replaces the deprecated `datetime.utcnow()`.

Returns *naive* UTC for backwards compatibility with existing rows in the
SQLite DB (those were written by `datetime.utcnow()`). When we migrate to
PostgreSQL with `DateTime(timezone=True)` columns, change `utc_now()` to
return TZ-aware (`datetime.now(timezone.utc)`) — that's the only edit needed
across the codebase.
"""
from datetime import date, datetime, timezone


def utc_now() -> datetime:
    """Current UTC instant as a naive datetime (no tzinfo).

    Equivalent to the deprecated `datetime.utcnow()` but uses the
    non-deprecated `datetime.now(timezone.utc)` under the hood.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_today() -> date:
    """Current UTC date."""
    return utc_now().date()
