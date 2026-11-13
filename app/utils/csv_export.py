"""CSV export helpers."""
import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from enum import Enum
from typing import Any

from fastapi.responses import StreamingResponse


def _fmt(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def rows_to_csv(rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> str:
    rows = list(rows)
    buffer = io.StringIO()
    if not rows and not fieldnames:
        return ""
    fieldnames = fieldnames or list(rows[0].keys())
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _fmt(row.get(k)) for k in fieldnames})
    return buffer.getvalue()


def csv_response(rows: Iterable[dict[str, Any]], filename: str) -> StreamingResponse:
    content = rows_to_csv(rows)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
