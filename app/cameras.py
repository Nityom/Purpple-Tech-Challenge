"""
cameras.py — Per-camera activity statistics.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import CameraStatsResponse, CameraStat


def get_camera_stats(store_id: str, db: Session, date: Optional[str] = None) -> CameraStatsResponse:
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    rows = db.execute(text("""
        SELECT
            camera_id,
            COUNT(*)                                          AS total_events,
            COUNT(DISTINCT visitor_id)                        AS unique_visitors,
            SUM(CASE WHEN event_type = 'ENTRY'   THEN 1 ELSE 0 END) AS entries,
            SUM(CASE WHEN event_type = 'EXIT'    THEN 1 ELSE 0 END) AS exits,
            SUM(CASE WHEN event_type = 'REENTRY' THEN 1 ELSE 0 END) AS reentries,
            SUM(CASE WHEN event_type LIKE 'ZONE%' THEN 1 ELSE 0 END) AS zone_events,
            SUM(CASE WHEN is_staff = TRUE THEN 1 ELSE 0 END)         AS staff_events,
            MIN(timestamp)  AS first_event_at,
            MAX(timestamp)  AS last_event_at
        FROM events
        WHERE store_id  = :store_id
          AND DATE(timestamp) = :date
        GROUP BY camera_id
        ORDER BY total_events DESC
    """), {"store_id": store_id, "date": date}).fetchall()

    cameras = [
        CameraStat(
            camera_id=r.camera_id,
            total_events=r.total_events,
            unique_visitors=r.unique_visitors,
            entries=r.entries,
            exits=r.exits,
            reentries=r.reentries,
            zone_events=r.zone_events,
            staff_events=r.staff_events,
            first_event_at=r.first_event_at,
            last_event_at=r.last_event_at,
        )
        for r in rows
    ]

    return CameraStatsResponse(store_id=store_id, date=date, cameras=cameras)
