"""
metrics.py — Real-time store metric computation.

All queries run directly against the events table — no caching.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import MetricsResponse, ZoneDwellMetric

_MIN_SESSIONS_FOR_CONFIDENCE = 20


def get_store_metrics(store_id: str, db: Session, date: Optional[str] = None) -> MetricsResponse:
    """
    Compute today's metrics for a store (or a specific date).
    All metrics exclude is_staff=TRUE events.
    """
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # -------------------------------------------------------------------
    # Unique visitors: distinct visitor_ids with an ENTRY event on this date
    # -------------------------------------------------------------------
    unique_visitors_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND event_type = 'ENTRY'
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    unique_visitors = unique_visitors_result.cnt if unique_visitors_result else 0

    # -------------------------------------------------------------------
    # Conversion rate: visitors in billing zone within 5 min before a POS txn
    # We count distinct visitor_ids that had a billing zone event
    # correlated with a POS transaction
    # -------------------------------------------------------------------
    converted_result = db.execute(text("""
        SELECT COUNT(DISTINCT e.visitor_id) AS cnt
        FROM events e
        INNER JOIN pos_transactions p
            ON p.store_id = e.store_id
           AND CAST((julianday(p.timestamp) - julianday(e.timestamp)) * 86400 AS INTEGER)
               BETWEEN 0 AND 300
        WHERE e.store_id = :store_id
          AND e.is_staff = FALSE
          AND e.zone_id IN ('BILLING', 'BILLING_QUEUE')
          AND DATE(e.timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    converted = converted_result.cnt if converted_result else 0

    conversion_rate = round(converted / unique_visitors, 4) if unique_visitors > 0 else 0.0

    # -------------------------------------------------------------------
    # Average dwell per zone
    # -------------------------------------------------------------------
    dwell_rows = db.execute(text("""
        SELECT zone_id,
               AVG(dwell_ms)  AS avg_dwell_ms,
               COUNT(*)       AS visit_count
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND event_type = 'ZONE_DWELL'
          AND zone_id IS NOT NULL
          AND DATE(timestamp) = :date
        GROUP BY zone_id
        ORDER BY avg_dwell_ms DESC
    """), {"store_id": store_id, "date": date}).fetchall()

    avg_dwell_by_zone = [
        ZoneDwellMetric(
            zone_id=row.zone_id,
            avg_dwell_ms=round(row.avg_dwell_ms, 1),
            visit_count=row.visit_count,
        )
        for row in dwell_rows
    ]

    # -------------------------------------------------------------------
    # Current queue depth: latest queue_depth value from BILLING events
    # -------------------------------------------------------------------
    queue_result = db.execute(text("""
        SELECT queue_depth
        FROM events
        WHERE store_id = :store_id
          AND queue_depth IS NOT NULL
          AND DATE(timestamp) = :date
        ORDER BY timestamp DESC
        LIMIT 1
    """), {"store_id": store_id, "date": date}).fetchone()
    current_queue_depth = queue_result.queue_depth if queue_result else 0

    # -------------------------------------------------------------------
    # Abandonment rate: BILLING_QUEUE_ABANDON / (BILLING_QUEUE_JOIN + BILLING_QUEUE_ABANDON)
    # -------------------------------------------------------------------
    abandon_result = db.execute(text("""
        SELECT
            SUM(CASE WHEN event_type = 'BILLING_QUEUE_ABANDON' THEN 1 ELSE 0 END) AS abandoned,
            SUM(CASE WHEN event_type IN ('BILLING_QUEUE_JOIN','BILLING_QUEUE_ABANDON') THEN 1 ELSE 0 END) AS total_billing
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()

    if abandon_result and abandon_result.total_billing and abandon_result.total_billing > 0:
        abandonment_rate = round(abandon_result.abandoned / abandon_result.total_billing, 4)
    else:
        abandonment_rate = 0.0

    # Session count for data confidence flag
    session_count_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    session_count = session_count_result.cnt if session_count_result else 0

    return MetricsResponse(
        store_id=store_id,
        date=date,
        unique_visitors=unique_visitors,
        conversion_rate=conversion_rate,
        avg_dwell_ms_by_zone=avg_dwell_by_zone,
        current_queue_depth=current_queue_depth or 0,
        abandonment_rate=abandonment_rate,
        data_confidence=session_count >= _MIN_SESSIONS_FOR_CONFIDENCE,
    )
