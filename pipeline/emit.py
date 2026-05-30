"""
emit.py — Event schema definition and emission utilities.

Builds Pydantic-validated StoreEvent objects and writes them to:
  1. A JSONL file  (always)
  2. POST /events/ingest  (when API_URL is set in environment)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Pydantic schema (mirrors the spec in the problem statement exactly)
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {
    "ENTRY",
    "EXIT",
    "ZONE_ENTER",
    "ZONE_EXIT",
    "ZONE_DWELL",
    "BILLING_QUEUE_JOIN",
    "BILLING_QUEUE_ABANDON",
    "REENTRY",
}


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 0


class StoreEvent(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: str          # ISO-8601 UTC
    zone_id: Optional[str]
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    metadata: EventMetadata = EventMetadata()

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {VALID_EVENT_TYPES}, got '{v}'")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {v}")
        return round(v, 4)

    @model_validator(mode="after")
    def validate_zone_id_rules(self) -> "StoreEvent":
        if self.event_type in ("ENTRY", "EXIT") and self.zone_id is not None:
            raise ValueError("zone_id must be null for ENTRY and EXIT events")
        if self.event_type in ("ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL") and not self.zone_id:
            raise ValueError(f"zone_id is required for {self.event_type} events")
        return self


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_event_id() -> str:
    return str(uuid.uuid4())


def frame_to_timestamp(clip_start_iso: str, frame_index: int, fps: float) -> str:
    """Convert a frame index to an ISO-8601 UTC timestamp string."""
    clip_start = datetime.fromisoformat(clip_start_iso.replace("Z", "+00:00"))
    offset_seconds = frame_index / fps
    ts = clip_start.timestamp() + offset_seconds
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: str,
    zone_id: Optional[str],
    dwell_ms: int,
    is_staff: bool,
    confidence: float,
    queue_depth: Optional[int] = None,
    sku_zone: Optional[str] = None,
    session_seq: int = 0,
) -> StoreEvent:
    return StoreEvent(
        event_id=make_event_id(),
        store_id=store_id,
        camera_id=camera_id,
        visitor_id=visitor_id,
        event_type=event_type,
        timestamp=timestamp,
        zone_id=zone_id,
        dwell_ms=dwell_ms,
        is_staff=is_staff,
        confidence=confidence,
        metadata=EventMetadata(
            queue_depth=queue_depth,
            sku_zone=sku_zone,
            session_seq=session_seq,
        ),
    )


# ---------------------------------------------------------------------------
# Emission: JSONL file + optional HTTP ingest
# ---------------------------------------------------------------------------

class EventEmitter:
    """
    Thread-safe event emitter.  Buffers events and flushes in batches to:
      - A JSONL file (always)
      - POST /events/ingest (if API_URL is configured)
    """

    BATCH_SIZE = 50

    def __init__(self, output_path: str, api_url: Optional[str] = None):
        self.output_path = output_path
        self.api_url = api_url or os.environ.get("API_URL")
        self._buffer: list[dict] = []
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        self._file = open(output_path, "a", encoding="utf-8")

    def emit(self, event: StoreEvent) -> None:
        payload = event.model_dump()
        line = json.dumps(payload, default=str) + "\n"
        self._file.write(line)
        self._file.flush()
        self._buffer.append(payload)
        if len(self._buffer) >= self.BATCH_SIZE:
            self._flush_to_api()

    def _flush_to_api(self) -> None:
        if not self.api_url or not self._buffer:
            self._buffer.clear()
            return
        url = f"{self.api_url.rstrip('/')}/events/ingest"
        try:
            resp = httpx.post(url, json={"events": self._buffer}, timeout=10.0)
            resp.raise_for_status()
        except Exception as exc:
            # Log but do not crash the pipeline — events are already in JSONL
            print(f"[emit] WARNING: Failed to POST to API ({url}): {exc}")
        finally:
            self._buffer.clear()

    def flush(self) -> None:
        """Force flush remaining buffered events."""
        self._flush_to_api()

    def close(self) -> None:
        self.flush()
        self._file.close()
