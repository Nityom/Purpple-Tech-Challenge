"""
funnel.py — Conversion funnel and session deduplication logic.

Session = distinct visitor_id per calendar day per store.
Re-entries (same visitor_id, multiple ENTRY events on same day) = same session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import FunnelResponse, FunnelStage


def get_store_funnel(store_id: str, db: Session, date: Optional[str] = None) -> FunnelResponse:
    """
    Compute the conversion funnel:
      Stage 1: ENTRY          — unique sessions that entered the store
      Stage 2: ZONE_VISIT     — sessions that visited at least one product zone
      Stage 3: BILLING_QUEUE  — sessions that entered the billing zone/queue
      Stage 4: PURCHASE       — sessions correlated with a POS transaction
    """
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # Stage 1: Sessions with an ENTRY event
    entry_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND event_type = 'ENTRY'
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    entry_count = entry_result.cnt if entry_result else 0

    # Stage 2: Sessions with at least one ZONE_ENTER for a product zone
    zone_visit_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND event_type = 'ZONE_ENTER'
          AND zone_id NOT IN ('ENTRY_EXIT', 'BILLING', 'BILLING_QUEUE')
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    zone_visit_count = zone_visit_result.cnt if zone_visit_result else 0

    # Stage 3: Sessions that entered billing zone
    billing_result = db.execute(text("""
        SELECT COUNT(DISTINCT visitor_id) AS cnt
        FROM events
        WHERE store_id = :store_id
          AND is_staff = FALSE
          AND zone_id IN ('BILLING', 'BILLING_QUEUE')
          AND event_type IN ('ZONE_ENTER', 'BILLING_QUEUE_JOIN')
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()
    billing_count = billing_result.cnt if billing_result else 0

    # Stage 4: Sessions with a correlated POS transaction (same logic as metrics.py)
    purchase_result = db.execute(text("""
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
    purchase_count = purchase_result.cnt if purchase_result else 0

    # total_sessions = max reach across entry + zone (multi-camera stores may
    # have more zone visitors than entry-camera captures)
    total_sessions = max(entry_count, zone_visit_count)

    def drop_off(prev: int, curr: int) -> float:
        if prev == 0:
            return 0.0
        # Clamp to 0 — zone counts can exceed entry count in multi-camera setups
        # (floor cameras see people not captured at entry). A negative drop-off
        # would be misleading; the funnel entry count is just a lower bound.
        return max(0.0, round((prev - curr) / prev * 100, 1))

    stages = [
        FunnelStage(
            stage="Entry",
            count=entry_count,
            drop_off_pct=0.0,
        ),
        FunnelStage(
            stage="Zone Visit",
            count=zone_visit_count,
            drop_off_pct=drop_off(entry_count, zone_visit_count),
        ),
        FunnelStage(
            stage="Billing Queue",
            count=billing_count,
            drop_off_pct=drop_off(zone_visit_count, billing_count),
        ),
        FunnelStage(
            stage="Purchase",
            count=purchase_count,
            drop_off_pct=drop_off(billing_count, purchase_count),
        ),
    ]

    return FunnelResponse(
        store_id=store_id,
        date=date,
        stages=stages,
        total_sessions=total_sessions,
    )
