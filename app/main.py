"""
main.py — FastAPI application entrypoint.

Endpoints:
  POST /events/ingest
  GET  /stores/{store_id}/metrics
  GET  /stores/{store_id}/funnel
  GET  /stores/{store_id}/heatmap
  GET  /stores/{store_id}/anomalies
  GET  /health
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.anomalies import get_anomalies
from app.cameras import get_camera_stats
from app.database import get_db, init_db, load_pos_transactions
from app.funnel import get_store_funnel
from app.health import get_health
from app.heatmap import get_heatmap
from app.ingestion import ingest_events
from app.logger import RequestLoggingMiddleware, logger
from app.metrics import get_store_metrics
from app.pos_analytics import get_pos_analytics
from app.models import (
    AnomaliesResponse,
    CameraStatsResponse,
    FunnelResponse,
    HealthResponse,
    HeatmapResponse,
    IngestRequest,
    IngestResponse,
    MetricsResponse,
    POSAnalyticsResponse,
)

# ---------------------------------------------------------------------------
# Lifespan: DB init + POS data load
# ---------------------------------------------------------------------------

POS_CSV_PATH = os.environ.get(
    "POS_CSV_PATH",
    "Brigade_Bangalore_10_April_26 (1)bc6219c.csv",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("database_initialised")

    # Load POS transactions from CSV
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        inserted = load_pos_transactions(POS_CSV_PATH, db)
        if inserted > 0:
            logger.info("pos_transactions_loaded", count=inserted, path=POS_CSV_PATH)
        else:
            logger.info("pos_transactions_skipped", path=POS_CSV_PATH)
    finally:
        db.close()

    yield
    logger.info("shutdown")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Store Intelligence API",
    description="Real-time retail store analytics from CCTV event streams",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)


# ---------------------------------------------------------------------------
# Global exception handlers — no raw stack traces in responses
# ---------------------------------------------------------------------------

@app.exception_handler(OperationalError)
async def db_error_handler(request: Request, exc: OperationalError):
    logger.error("database_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"error": "database_unavailable", "message": "Service temporarily unavailable"},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "validation_error", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", error=type(exc).__name__, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "message": "An unexpected error occurred"},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/events/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of store events (idempotent by event_id)",
)
def ingest(
    request: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Accept up to 500 events per batch.
    Idempotent: sending the same batch twice produces the same result.
    Returns partial success when some events in the batch are malformed.
    """
    try:
        result = ingest_events(request, db)
        logger.info(
            "events_ingested",
            ingested=result.ingested_count,
            duplicates=result.duplicate_count,
            failed=len(result.failed_events),
        )
        return result
    except OperationalError:
        raise
    except Exception as exc:
        logger.error("ingest_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ingest_failed", "message": str(exc)},
        )


@app.get(
    "/stores/{store_id}/metrics",
    response_model=MetricsResponse,
    summary="Real-time store metrics for today",
)
def store_metrics(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> MetricsResponse:
    """
    Returns unique visitors, conversion rate, avg dwell per zone,
    queue depth, and abandonment rate. Excludes staff events.
    """
    return get_store_metrics(store_id, db, date)


@app.get(
    "/stores/{store_id}/funnel",
    response_model=FunnelResponse,
    summary="Conversion funnel for the store",
)
def store_funnel(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> FunnelResponse:
    """
    Entry → Zone Visit → Billing Queue → Purchase with counts and drop-off %.
    Sessions (not raw events) are the unit. Re-entries do not double-count visitors.
    """
    return get_store_funnel(store_id, db, date)


@app.get(
    "/stores/{store_id}/heatmap",
    response_model=HeatmapResponse,
    summary="Zone visit frequency heatmap",
)
def store_heatmap(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> HeatmapResponse:
    """
    Zone visit frequency + average dwell, normalised 0–100.
    Includes data_confidence=False if fewer than 20 sessions in the window.
    """
    return get_heatmap(store_id, db, date)


@app.get(
    "/stores/{store_id}/anomalies",
    response_model=AnomaliesResponse,
    summary="Active operational anomalies",
)
def store_anomalies(
    store_id: str,
    db: Session = Depends(get_db),
) -> AnomaliesResponse:
    return get_anomalies(store_id, db)


@app.get(
    "/stores/{store_id}/cameras",
    response_model=CameraStatsResponse,
    summary="Per-camera activity breakdown",
)
def store_cameras(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> CameraStatsResponse:
    return get_camera_stats(store_id, db, date)


@app.get(
    "/stores/{store_id}/pos",
    response_model=POSAnalyticsResponse,
    summary="POS revenue and product analytics",
)
def store_pos(
    store_id: str,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> POSAnalyticsResponse:
    return get_pos_analytics(store_id, db, date)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health and feed status",
)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Returns service status, last event timestamp per store, and STALE_FEED
    warnings for cameras that haven't sent events in 10+ minutes.
    """
    return get_health(db)
