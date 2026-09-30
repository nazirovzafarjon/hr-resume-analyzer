"""Small query helpers shared by the paginated admin listings."""

from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input only ever matches literally.

    The value is still passed as a bound parameter (never interpolated into
    SQL); this only stops ``%`` / ``_`` typed into a search box from acting as
    wildcards. Use together with ``ilike(pattern, escape="\\\\")``.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains_pattern(value: str) -> str:
    """``%value%`` pattern for a case-insensitive "contains" search."""
    return f"%{escape_like(value.strip())}%"


def paginate(db: Session, stmt: Select[Any], page: int, limit: int) -> tuple[list[Any], int]:
    """Run ``stmt`` for one page and return ``(rows, total)``.

    The total is counted over the same filtered statement (ordering removed)
    so the pagination bar always matches the rows the filters select.
    """
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * limit).limit(limit)).all()
    return list(rows), int(total)
