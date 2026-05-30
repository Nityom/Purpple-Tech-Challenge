"""
health.py — Service health endpoint logic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import HealthResponse, StoreHealth

STALE_FEED_THRESHOLD_MINUTES = 10


def get_health(db: Session) -> HealthResponse:
    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    db_status = "ok"
    stores: list[StoreHealth] = []

    try:
        # All stores seen in the database
        store_rows = db.execute(text("""
            SELECT DISTINCT store_id FROM events
        """)).fetchall()

        for row in store_rows:
            store_id = row.store_id

            last_event_result = db.execute(text("""
                SELECT MAX(timestamp) AS last_ts
                FROM events
                WHERE store_id = :store_id
            """), {"store_id": store_id}).fetchone()

            last_event_at = last_event_result.last_ts if last_event_result else None

            events_last_hour_result = db.execute(text("""
                SELECT COUNT(*) AS cnt
                FROM events
                WHERE store_id = :store_id
                  AND CAST(
                      (julianday(:now) - julianday(timestamp)) * 1440
                      AS INTEGER) <= 60
            """), {"store_id": store_id, "now": now_iso}).fetchone()
            events_last_hour = events_last_hour_result.cnt if events_last_hour_result else 0

            stale_feed = False
            if last_event_at:
                elapsed_min = (
                    datetime.now(tz=timezone.utc) -
                    datetime.fromisoformat(last_event_at.replace("Z", "+00:00"))
                ).total_seconds() / 60
                stale_feed = elapsed_min > STALE_FEED_THRESHOLD_MINUTES

            stores.append(StoreHealth(
                store_id=store_id,
                last_event_at=last_event_at,
                events_last_hour=events_last_hour,
                stale_feed=stale_feed,
            ))

    except Exception as exc:
        db_status = f"error: {exc}"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        checked_at=now_iso,
        stores=stores,
        database=db_status,
    )
