"""
ingestion.py — Event ingest, validation, and deduplication.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import EventRecord
from app.models import FailedEvent, IngestRequest, IngestResponse, StoreEvent


def ingest_events(request: IngestRequest, db: Session) -> IngestResponse:
    """
    Ingest a batch of events.
    - Deduplicates by event_id (INSERT OR IGNORE behaviour)
    - Validates each event individually
    - Returns partial success: valid events committed even if some fail
    """
    ingested = 0
    duplicates = 0
    failed: list[FailedEvent] = []

    for event in request.events:
        try:
            record = _event_to_record(event)
            db.add(record)
            db.flush()   # detect constraint violations immediately
            ingested += 1
        except IntegrityError:
            db.rollback()
            duplicates += 1
        except Exception as exc:
            db.rollback()
            failed.append(FailedEvent(
                event_id=getattr(event, "event_id", None),
                error=str(exc),
            ))

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        # Re-try one by one to salvage partial batch
        ingested, duplicates, failed = _fallback_one_by_one(request.events, db)

    return IngestResponse(
        ingested_count=ingested,
        duplicate_count=duplicates,
        failed_events=failed,
    )


def _event_to_record(event: StoreEvent) -> EventRecord:
    return EventRecord(
        event_id=event.event_id,
        store_id=event.store_id,
        camera_id=event.camera_id,
        visitor_id=event.visitor_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        zone_id=event.zone_id,
        dwell_ms=event.dwell_ms,
        is_staff=event.is_staff,
        confidence=event.confidence,
        queue_depth=event.metadata.queue_depth,
        sku_zone=event.metadata.sku_zone,
        session_seq=event.metadata.session_seq,
    )


def _fallback_one_by_one(
    events: list[StoreEvent], db: Session
) -> tuple[int, int, list[FailedEvent]]:
    ingested = 0
    duplicates = 0
    failed: list[FailedEvent] = []
    for event in events:
        try:
            record = _event_to_record(event)
            db.add(record)
            db.commit()
            ingested += 1
        except IntegrityError:
            db.rollback()
            duplicates += 1
        except Exception as exc:
            db.rollback()
            failed.append(FailedEvent(event_id=event.event_id, error=str(exc)))
    return ingested, duplicates, failed
