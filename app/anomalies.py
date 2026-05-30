"""
anomalies.py — Real-time anomaly detection for store operations.

Detected anomalies:
  BILLING_QUEUE_SPIKE    — queue depth exceeds threshold for sustained period
  CONVERSION_DROP        — today's conversion rate drops below 7-day avg - 2σ
  DEAD_ZONE              — no ZONE_ENTER events for any zone in 30+ minutes
  STALE_FEED             — no events received from a camera in 10+ minutes
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Anomaly, AnomaliesResponse

# Thresholds
QUEUE_SPIKE_WARN = 5
QUEUE_SPIKE_CRITICAL = 8
QUEUE_SPIKE_SUSTAIN_MINUTES = 3

STALE_FEED_WARN_MINUTES = 10
STALE_FEED_CRITICAL_MINUTES = 30

DEAD_ZONE_MINUTES = 30

STORE_OPEN_HOUR = 10
STORE_CLOSE_HOUR = 22


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_anomaly(
    anomaly_type: str,
    severity: str,
    description: str,
    suggested_action: str,
    store_id: str,
    metadata: Optional[dict] = None,
) -> Anomaly:
    return Anomaly(
        anomaly_id=str(uuid.uuid4()),
        anomaly_type=anomaly_type,
        severity=severity,
        description=description,
        suggested_action=suggested_action,
        detected_at=_now_iso(),
        store_id=store_id,
        metadata=metadata or {},
    )


def get_anomalies(store_id: str, db: Session) -> AnomaliesResponse:
    anomalies: list[Anomaly] = []
    now_iso = _now_iso()
    today = now_iso[:10]

    # -------------------------------------------------------------------
    # 1. BILLING_QUEUE_SPIKE
    # -------------------------------------------------------------------
    spike_result = db.execute(text("""
        SELECT MAX(queue_depth) AS max_depth,
               AVG(queue_depth) AS avg_depth,
               COUNT(*)         AS reading_count
        FROM events
        WHERE store_id = :store_id
          AND queue_depth IS NOT NULL
          AND CAST(
              (julianday(:now) - julianday(timestamp)) * 1440
              AS INTEGER) <= :window_min
    """), {
        "store_id": store_id,
        "now": now_iso,
        "window_min": QUEUE_SPIKE_SUSTAIN_MINUTES,
    }).fetchone()

    if spike_result and spike_result.max_depth is not None:
        max_depth = spike_result.max_depth
        if max_depth >= QUEUE_SPIKE_CRITICAL:
            anomalies.append(_make_anomaly(
                anomaly_type="BILLING_QUEUE_SPIKE",
                severity="CRITICAL",
                description=f"Billing queue depth reached {max_depth} — critical threshold exceeded.",
                suggested_action="Immediately open an additional billing counter or call shift supervisor.",
                store_id=store_id,
                metadata={"max_queue_depth": max_depth, "window_minutes": QUEUE_SPIKE_SUSTAIN_MINUTES},
            ))
        elif max_depth >= QUEUE_SPIKE_WARN:
            anomalies.append(_make_anomaly(
                anomaly_type="BILLING_QUEUE_SPIKE",
                severity="WARN",
                description=f"Billing queue depth at {max_depth} for past {QUEUE_SPIKE_SUSTAIN_MINUTES} minutes.",
                suggested_action="Monitor queue. Consider opening an additional billing counter.",
                store_id=store_id,
                metadata={"max_queue_depth": max_depth, "window_minutes": QUEUE_SPIKE_SUSTAIN_MINUTES},
            ))

    # -------------------------------------------------------------------
    # 2. CONVERSION_DROP vs 7-day rolling average
    # -------------------------------------------------------------------
    history_result = db.execute(text("""
        WITH daily_conversions AS (
            SELECT DATE(e.timestamp) AS day,
                   COUNT(DISTINCT e.visitor_id) AS converted,
                   (SELECT COUNT(DISTINCT visitor_id)
                    FROM events e2
                    WHERE e2.store_id = e.store_id
                      AND e2.is_staff = FALSE
                      AND e2.event_type = 'ENTRY'
                      AND DATE(e2.timestamp) = DATE(e.timestamp)) AS total_visitors
            FROM events e
            INNER JOIN pos_transactions p
                ON p.store_id = e.store_id
               AND CAST((julianday(p.timestamp) - julianday(e.timestamp)) * 86400 AS INTEGER)
                   BETWEEN 0 AND 300
            WHERE e.store_id = :store_id
              AND e.is_staff = FALSE
              AND e.zone_id IN ('BILLING', 'BILLING_QUEUE')
              AND DATE(e.timestamp) >= DATE(:today, '-7 days')
              AND DATE(e.timestamp) < :today
            GROUP BY DATE(e.timestamp)
        )
        SELECT AVG(CAST(converted AS FLOAT) / NULLIF(total_visitors, 0)) AS avg_rate,
               COUNT(*) AS days_with_data
        FROM daily_conversions
    """), {"store_id": store_id, "today": today}).fetchone()

    if history_result and history_result.avg_rate is not None and history_result.days_with_data >= 2:
        avg_7d = history_result.avg_rate

        # Today's conversion rate
        today_result = db.execute(text("""
            SELECT
                COUNT(DISTINCT e.visitor_id) AS converted,
                (SELECT COUNT(DISTINCT visitor_id)
                 FROM events e2
                 WHERE e2.store_id = :store_id
                   AND e2.is_staff = FALSE
                   AND e2.event_type = 'ENTRY'
                   AND DATE(e2.timestamp) = :today) AS total_visitors
            FROM events e
            INNER JOIN pos_transactions p
                ON p.store_id = e.store_id
               AND CAST((julianday(p.timestamp) - julianday(e.timestamp)) * 86400 AS INTEGER)
                   BETWEEN 0 AND 300
            WHERE e.store_id = :store_id
              AND e.is_staff = FALSE
              AND e.zone_id IN ('BILLING', 'BILLING_QUEUE')
              AND DATE(e.timestamp) = :today
        """), {"store_id": store_id, "today": today}).fetchone()

        if today_result and today_result.total_visitors and today_result.total_visitors > 0:
            today_rate = today_result.converted / today_result.total_visitors
            # Flag if today is more than 20 percentage points below 7-day avg
            if today_rate < (avg_7d - 0.20):
                anomalies.append(_make_anomaly(
                    anomaly_type="CONVERSION_DROP",
                    severity="WARN",
                    description=(
                        f"Conversion rate today ({today_rate:.1%}) is significantly below "
                        f"7-day average ({avg_7d:.1%})."
                    ),
                    suggested_action=(
                        "Review billing queue length and abandonment rate. "
                        "Check if any product zones have unusually low dwell time."
                    ),
                    store_id=store_id,
                    metadata={
                        "today_rate": round(today_rate, 4),
                        "avg_7d_rate": round(avg_7d, 4),
                    },
                ))

    # -------------------------------------------------------------------
    # 3. DEAD_ZONE — no zone visits in past 30 minutes during open hours
    # -------------------------------------------------------------------
    now_dt = datetime.now(tz=timezone.utc)
    if STORE_OPEN_HOUR <= now_dt.hour < STORE_CLOSE_HOUR:
        dead_zone_result = db.execute(text("""
            SELECT zone_id,
                   MAX(timestamp) AS last_visit
            FROM events
            WHERE store_id = :store_id
              AND is_staff = FALSE
              AND event_type = 'ZONE_ENTER'
              AND zone_id NOT IN ('ENTRY_EXIT')
              AND DATE(timestamp) = :today
            GROUP BY zone_id
        """), {"store_id": store_id, "today": today}).fetchall()

        for row in dead_zone_result:
            if row.last_visit:
                elapsed_minutes = (
                    datetime.now(tz=timezone.utc) -
                    datetime.fromisoformat(row.last_visit.replace("Z", "+00:00"))
                ).total_seconds() / 60
                if elapsed_minutes >= DEAD_ZONE_MINUTES:
                    anomalies.append(_make_anomaly(
                        anomaly_type="DEAD_ZONE",
                        severity="INFO",
                        description=(
                            f"No visitors in zone '{row.zone_id}' for "
                            f"{int(elapsed_minutes)} minutes."
                        ),
                        suggested_action=(
                            f"Verify zone '{row.zone_id}' signage and product placement. "
                            "Check if camera feed is active."
                        ),
                        store_id=store_id,
                        metadata={"zone_id": row.zone_id, "minutes_inactive": int(elapsed_minutes)},
                    ))

    # -------------------------------------------------------------------
    # 4. STALE_FEED — no events from a camera in 10+ minutes
    # -------------------------------------------------------------------
    camera_result = db.execute(text("""
        SELECT camera_id,
               MAX(timestamp) AS last_event_at
        FROM events
        WHERE store_id = :store_id
          AND DATE(timestamp) = :today
        GROUP BY camera_id
    """), {"store_id": store_id, "today": today}).fetchall()

    for row in camera_result:
        if row.last_event_at:
            elapsed_min = (
                datetime.now(tz=timezone.utc) -
                datetime.fromisoformat(row.last_event_at.replace("Z", "+00:00"))
            ).total_seconds() / 60
            if elapsed_min >= STALE_FEED_CRITICAL_MINUTES:
                anomalies.append(_make_anomaly(
                    anomaly_type="STALE_FEED",
                    severity="CRITICAL",
                    description=(
                        f"Camera '{row.camera_id}' has not sent events in "
                        f"{int(elapsed_min)} minutes."
                    ),
                    suggested_action=(
                        "Check camera hardware and network connection. "
                        "Escalate to facilities team if issue persists."
                    ),
                    store_id=store_id,
                    metadata={"camera_id": row.camera_id, "minutes_stale": int(elapsed_min)},
                ))
            elif elapsed_min >= STALE_FEED_WARN_MINUTES:
                anomalies.append(_make_anomaly(
                    anomaly_type="STALE_FEED",
                    severity="WARN",
                    description=(
                        f"Camera '{row.camera_id}' has not sent events in "
                        f"{int(elapsed_min)} minutes."
                    ),
                    suggested_action=(
                        "Monitor camera feed. Restart detection pipeline if events don't resume."
                    ),
                    store_id=store_id,
                    metadata={"camera_id": row.camera_id, "minutes_stale": int(elapsed_min)},
                ))

    return AnomaliesResponse(
        store_id=store_id,
        checked_at=now_iso,
        anomalies=anomalies,
    )
