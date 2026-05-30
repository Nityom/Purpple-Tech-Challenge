"""
models.py — Pydantic schemas for events, API requests, and responses.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Event schema (identical to pipeline/emit.py — single source of truth)
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
    timestamp: str
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    metadata: EventMetadata = EventMetadata()

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"Unknown event_type: '{v}'")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0]")
        return round(v, 6)

    @model_validator(mode="after")
    def validate_zone_id(self) -> "StoreEvent":
        if self.event_type in ("ENTRY", "EXIT") and self.zone_id is not None:
            raise ValueError("zone_id must be null for ENTRY/EXIT events")
        return self


# ---------------------------------------------------------------------------
# Ingest request/response
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    events: list[StoreEvent]

    @field_validator("events")
    @classmethod
    def max_batch_size(cls, v: list) -> list:
        if len(v) > 500:
            raise ValueError("Batch size cannot exceed 500 events")
        return v


class FailedEvent(BaseModel):
    event_id: Optional[str]
    error: str


class IngestResponse(BaseModel):
    ingested_count: int
    duplicate_count: int
    failed_events: list[FailedEvent]


# ---------------------------------------------------------------------------
# Metrics response
# ---------------------------------------------------------------------------

class ZoneDwellMetric(BaseModel):
    zone_id: str
    avg_dwell_ms: float
    visit_count: int


class MetricsResponse(BaseModel):
    store_id: str
    date: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_ms_by_zone: list[ZoneDwellMetric]
    current_queue_depth: int
    abandonment_rate: float
    data_confidence: bool  # False if < 20 sessions


# ---------------------------------------------------------------------------
# Funnel response
# ---------------------------------------------------------------------------

class FunnelStage(BaseModel):
    stage: str
    count: int
    drop_off_pct: float


class FunnelResponse(BaseModel):
    store_id: str
    date: str
    stages: list[FunnelStage]
    total_sessions: int


# ---------------------------------------------------------------------------
# Heatmap response
# ---------------------------------------------------------------------------

class HeatmapZone(BaseModel):
    zone_id: str
    visit_frequency: int
    avg_dwell_ms: float
    normalised_score: float  # 0–100


class HeatmapResponse(BaseModel):
    store_id: str
    date: str
    zones: list[HeatmapZone]
    data_confidence: bool


# ---------------------------------------------------------------------------
# Anomaly response
# ---------------------------------------------------------------------------

class Anomaly(BaseModel):
    anomaly_id: str
    anomaly_type: str
    severity: str         # INFO / WARN / CRITICAL
    description: str
    suggested_action: str
    detected_at: str
    store_id: str
    metadata: dict[str, Any] = {}


class AnomaliesResponse(BaseModel):
    store_id: str
    checked_at: str
    anomalies: list[Anomaly]


# ---------------------------------------------------------------------------
# Health response
# ---------------------------------------------------------------------------

class StoreHealth(BaseModel):
    store_id: str
    last_event_at: Optional[str]
    events_last_hour: int
    stale_feed: bool


class HealthResponse(BaseModel):
    status: str
    checked_at: str
    stores: list[StoreHealth]
    database: str


# ---------------------------------------------------------------------------
# Camera stats response
# ---------------------------------------------------------------------------

class CameraStat(BaseModel):
    camera_id: str
    total_events: int
    unique_visitors: int
    entries: int
    exits: int
    reentries: int
    zone_events: int
    staff_events: int
    first_event_at: Optional[str]
    last_event_at: Optional[str]


class CameraStatsResponse(BaseModel):
    store_id: str
    date: str
    cameras: list[CameraStat]


# ---------------------------------------------------------------------------
# POS analytics response
# ---------------------------------------------------------------------------

class POSHourly(BaseModel):
    hour: int
    transactions: int
    revenue: float


class POSProduct(BaseModel):
    product_name: str
    brand: str
    qty_sold: int
    revenue: float


class POSCategory(BaseModel):
    category: str
    sub_category: str
    qty_sold: int
    revenue: float


class POSAnalyticsResponse(BaseModel):
    store_id: str
    date: str
    total_transactions: int
    total_revenue: float
    avg_basket_inr: float
    hourly: list[POSHourly]
    top_products: list[POSProduct]
    top_categories: list[POSCategory]

