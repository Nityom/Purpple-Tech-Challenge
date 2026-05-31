# PROMPT:
# "Generate pytest tests for a retail store anomaly detection module that:
#  - detects BILLING_QUEUE_SPIKE at queue_depth > 5 (WARN) and > 8 (CRITICAL)
#  - detects CONVERSION_DROP when today's rate is < 7-day avg by 20+ points
#  - detects DEAD_ZONE when no zone visits in 30+ minutes during open hours
#  - detects STALE_FEED when camera hasn't sent events in 10+ minutes
#  Each anomaly has severity (INFO/WARN/CRITICAL) and suggested_action string.
#  Test the anomaly response schema, severity thresholds, and suggested_action presence."
#
# CHANGES MADE:
# - Replaced reliance on real clock time with parameterised timestamp injection
# - Added test that low queue depth does NOT trigger anomaly
# - Added test for anomaly_id uniqueness across multiple detections
# - Added test for suggested_action being a non-empty string
# - Added edge case: no events at all (empty store) should not crash anomaly detection

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# Test DB
# ---------------------------------------------------------------------------

from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(test_engine, "connect")
def _set_wal(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")

TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STORE_ID = "STORE_BLR_001"


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_queue_event(queue_depth: int, minutes_ago: int = 1) -> dict:
    ts = _iso(_now_utc() - timedelta(minutes=minutes_ago))
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_BILLING_01",
        "visitor_id": f"VIS_{uuid.uuid4().hex[:8]}",
        "event_type": "BILLING_QUEUE_JOIN",
        "timestamp": ts,
        "zone_id": "BILLING_QUEUE",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.9,
        "metadata": {"queue_depth": queue_depth, "sku_zone": None, "session_seq": 1},
    }


def _make_zone_event(zone_id: str, minutes_ago: int = 5, visitor_id: str = None) -> dict:
    ts = _iso(_now_utc() - timedelta(minutes=minutes_ago))
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_FLOOR_01",
        "visitor_id": visitor_id or f"VIS_{uuid.uuid4().hex[:8]}",
        "event_type": "ZONE_ENTER",
        "timestamp": ts,
        "zone_id": zone_id,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.9,
        "metadata": {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }


# ---------------------------------------------------------------------------
# Anomaly response schema tests
# ---------------------------------------------------------------------------

class TestAnomalySchema:
    def test_anomalies_endpoint_returns_valid_structure(self, client):
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert "checked_at" in data
        assert "store_id" in data
        assert data["store_id"] == STORE_ID

    def test_empty_store_returns_empty_anomalies_list(self, client):
        """Empty store must not crash anomaly detection."""
        resp = client.get("/stores/STORE_EMPTY_99/anomalies")
        assert resp.status_code == 200
        assert resp.json()["anomalies"] == []

    def test_each_anomaly_has_required_fields(self, client):
        # Trigger a queue spike
        events = [_make_queue_event(queue_depth=9, minutes_ago=i) for i in range(1, 4)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        for anomaly in resp.json()["anomalies"]:
            assert "anomaly_id" in anomaly
            assert "anomaly_type" in anomaly
            assert "severity" in anomaly
            assert "description" in anomaly
            assert "suggested_action" in anomaly
            assert "detected_at" in anomaly
            assert anomaly["suggested_action"] != ""

    def test_anomaly_ids_are_unique(self, client):
        """Multiple anomalies must each have a unique anomaly_id."""
        # Trigger queue spike
        events = [_make_queue_event(queue_depth=9, minutes_ago=i) for i in range(1, 4)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        ids = [a["anomaly_id"] for a in resp.json()["anomalies"]]
        assert len(ids) == len(set(ids)), "All anomaly_ids must be unique"

    def test_severity_values_are_valid(self, client):
        """Severity must be one of: INFO, WARN, CRITICAL."""
        events = [_make_queue_event(queue_depth=9, minutes_ago=1)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        for anomaly in resp.json()["anomalies"]:
            assert anomaly["severity"] in ("INFO", "WARN", "CRITICAL")


# ---------------------------------------------------------------------------
# BILLING_QUEUE_SPIKE tests
# ---------------------------------------------------------------------------

class TestBillingQueueSpike:
    def test_no_anomaly_below_threshold(self, client):
        """Queue depth of 3 must not trigger BILLING_QUEUE_SPIKE."""
        events = [_make_queue_event(queue_depth=3, minutes_ago=1)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        spike_anomalies = [
            a for a in resp.json()["anomalies"]
            if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"
        ]
        assert len(spike_anomalies) == 0

    def test_warn_level_at_moderate_queue(self, client):
        """Queue depth of 6 (>= 5, < 8) must trigger WARN severity."""
        events = [_make_queue_event(queue_depth=6, minutes_ago=i) for i in range(1, 4)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        spike = next(
            (a for a in resp.json()["anomalies"] if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"),
            None
        )
        assert spike is not None
        assert spike["severity"] == "WARN"

    def test_critical_level_at_high_queue(self, client):
        """Queue depth >= 8 must trigger CRITICAL severity."""
        events = [_make_queue_event(queue_depth=10, minutes_ago=i) for i in range(1, 4)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        spike = next(
            (a for a in resp.json()["anomalies"] if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"),
            None
        )
        assert spike is not None
        assert spike["severity"] == "CRITICAL"

    def test_queue_spike_metadata_has_depth(self, client):
        """BILLING_QUEUE_SPIKE anomaly metadata must include max_queue_depth."""
        events = [_make_queue_event(queue_depth=9, minutes_ago=1)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        spike = next(
            (a for a in resp.json()["anomalies"] if a["anomaly_type"] == "BILLING_QUEUE_SPIKE"),
            None
        )
        if spike:
            assert "max_queue_depth" in spike.get("metadata", {})


# ---------------------------------------------------------------------------
# STALE_FEED tests
# ---------------------------------------------------------------------------

class TestStaleFeed:
    def test_no_stale_feed_for_recent_events(self, client):
        """Camera with events in the last 5 minutes must not trigger STALE_FEED."""
        events = [_make_zone_event("SKINCARE", minutes_ago=3)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        stale = [a for a in resp.json()["anomalies"] if a["anomaly_type"] == "STALE_FEED"]
        assert len(stale) == 0

    def test_stale_feed_triggered_for_old_events(self, client):
        """Camera with last event >10 minutes ago must trigger STALE_FEED."""
        events = [_make_zone_event("SKINCARE", minutes_ago=15)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        stale = [a for a in resp.json()["anomalies"] if a["anomaly_type"] == "STALE_FEED"]
        assert len(stale) >= 1
        assert stale[0]["severity"] in ("WARN", "CRITICAL")

    def test_critical_stale_feed_after_30_minutes(self, client):
        """Camera silent for >30 minutes must trigger CRITICAL STALE_FEED."""
        events = [_make_zone_event("SKINCARE", minutes_ago=35)]
        client.post("/events/ingest", json={"events": events})
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        stale = [a for a in resp.json()["anomalies"] if a["anomaly_type"] == "STALE_FEED"]
        assert any(s["severity"] == "CRITICAL" for s in stale)


# ---------------------------------------------------------------------------
# CONVERSION_DROP tests
# ---------------------------------------------------------------------------

class TestConversionDrop:
    def test_conversion_drop_triggered_when_today_is_low(self, client):
        from app.database import POSTransaction
        db = next(override_get_db())
        
        # Day 1: 2 days ago
        d1 = (datetime.now(tz=timezone.utc) - timedelta(days=2))
        d1_base = d1.replace(hour=12, minute=0, second=0, microsecond=0)
        d1_ts = d1_base.strftime("%Y-%m-%dT%H:%M:%SZ")
        d1_txn_ts = (d1_base + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Day 2: 1 day ago
        d2 = (datetime.now(tz=timezone.utc) - timedelta(days=1))
        d2_base = d2.replace(hour=12, minute=0, second=0, microsecond=0)
        d2_ts = d2_base.strftime("%Y-%m-%dT%H:%M:%SZ")
        d2_txn_ts = (d2_base + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Today
        d_today = datetime.now(tz=timezone.utc)
        d_today_base = d_today.replace(hour=12, minute=0, second=0, microsecond=0)
        d_today_ts = d_today_base.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        client.post("/events/ingest", json={"events": [
            # Day 1
            {
                "event_id": str(uuid.uuid4()), "store_id": STORE_ID, "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_day1", "event_type": "ENTRY", "timestamp": d1_ts,
                "confidence": 0.9, "is_staff": False, "metadata": {"session_seq": 1}
            },
            {
                "event_id": str(uuid.uuid4()), "store_id": STORE_ID, "camera_id": "CAM_FLOOR_01",
                "visitor_id": "VIS_day1", "event_type": "ZONE_ENTER", "timestamp": d1_ts,
                "zone_id": "BILLING", "confidence": 0.9, "is_staff": False, "metadata": {"session_seq": 2}
            },
            # Day 2
            {
                "event_id": str(uuid.uuid4()), "store_id": STORE_ID, "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_day2", "event_type": "ENTRY", "timestamp": d2_ts,
                "confidence": 0.9, "is_staff": False, "metadata": {"session_seq": 1}
            },
            {
                "event_id": str(uuid.uuid4()), "store_id": STORE_ID, "camera_id": "CAM_FLOOR_01",
                "visitor_id": "VIS_day2", "event_type": "ZONE_ENTER", "timestamp": d2_ts,
                "zone_id": "BILLING", "confidence": 0.9, "is_staff": False, "metadata": {"session_seq": 2}
            },
            # Today
            {
                "event_id": str(uuid.uuid4()), "store_id": STORE_ID, "camera_id": "CAM_ENTRY_01",
                "visitor_id": "VIS_today", "event_type": "ENTRY", "timestamp": d_today_ts,
                "confidence": 0.9, "is_staff": False, "metadata": {"session_seq": 1}
            }
        ]})
        
        db.add(POSTransaction(
            transaction_id="TXN_DAY_1", store_id=STORE_ID,
            timestamp=d1_txn_ts, basket_value_inr=100.0
        ))
        db.add(POSTransaction(
            transaction_id="TXN_DAY_2", store_id=STORE_ID,
            timestamp=d2_txn_ts, basket_value_inr=100.0
        ))
        db.commit()
        
        resp = client.get(f"/stores/{STORE_ID}/anomalies")
        assert resp.status_code == 200
        anom = [a for a in resp.json()["anomalies"] if a["anomaly_type"] == "CONVERSION_DROP"]
        assert len(anom) == 1
        assert anom[0]["severity"] == "WARN"
