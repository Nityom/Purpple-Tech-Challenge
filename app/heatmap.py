"""
heatmap.py — Zone visit frequency and average dwell, normalised 0-100.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import HeatmapResponse, HeatmapZone

_MIN_SESSIONS_FOR_CONFIDENCE = 20


def get_heatmap(store_id: str, db: Session, date: Optional[str] = None) -> HeatmapResponse:
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    rows = db.execute(text("""
        SELECT zone_id,
               COUNT(DISTINCT visitor_id) AS visit_frequency,
               AVG(dwell_ms)              AS avg_dwell_ms
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
          AND zone_id IS NOT NULL
          AND zone_id NOT IN ('ENTRY_EXIT')
          AND DATE(timestamp) = :date
        GROUP BY zone_id
    """), {"store_id": store_id, "date": date}).fetchall()

    if not rows:
        session_result = db.execute(text("""
            SELECT COUNT(DISTINCT visitor_id) AS cnt
            FROM events
            WHERE store_id = :store_id AND is_staff = FALSE AND DATE(timestamp) = :date
        """), {"store_id": store_id, "date": date}).fetchone()
        session_count = session_result.cnt if session_result else 0
        return HeatmapResponse(
            store_id=store_id,
            date=date,
            zones=[],
            data_confidence=session_count >= _MIN_SESSIONS_FOR_CONFIDENCE,
        )

    max_freq = max(row.visit_frequency for row in rows) or 1

    zones = [
        HeatmapZone(
            zone_id=row.zone_id,
            visit_frequency=row.visit_frequency,
            avg_dwell_ms=round(row.avg_dwell_ms or 0, 1),
            normalised_score=round(row.visit_frequency / max_freq * 100, 1),
        )
        for row in rows
    ]
    zones.sort(key=lambda z: z.normalised_score, reverse=True)

    session_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id AND is_staff = FALSE AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    session_count = session_result.cnt if session_result else 0

    return HeatmapResponse(
        store_id=store_id,
        date=date,
        zones=zones,
        data_confidence=session_count >= _MIN_SESSIONS_FOR_CONFIDENCE,
    )
