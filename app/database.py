"""
database.py — SQLAlchemy setup with SQLite default, PostgreSQL via DATABASE_URL.

Tables:
  events            — all ingested store events
  pos_transactions  — POS transaction records (loaded from CSV at startup)
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///./store_intelligence.db"
)

# SQLite-specific: enable WAL mode for concurrent reads + writes
_engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Enable WAL for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, _conn_rec):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False)
    store_id = Column(String, nullable=False, index=True)
    camera_id = Column(String, nullable=False)
    visitor_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    timestamp = Column(String, nullable=False)         # ISO-8601 UTC
    zone_id = Column(String, nullable=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Boolean, default=False)
    confidence = Column(Float, nullable=False)
    queue_depth = Column(Integer, nullable=True)
    sku_zone = Column(String, nullable=True)
    session_seq = Column(Integer, default=0)
    created_at = Column(String, default=lambda: _now_iso())

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_id"),
        Index("ix_events_store_ts", "store_id", "timestamp"),
        Index("ix_events_visitor", "visitor_id", "store_id"),
        Index("ix_events_store_type", "store_id", "event_type"),
    )


class POSTransaction(Base):
    __tablename__ = "pos_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False)
    store_id = Column(String, nullable=False, index=True)
    timestamp = Column(String, nullable=False)          # ISO-8601 UTC
    basket_value_inr = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_transaction_id"),
        Index("ix_pos_store_ts", "store_id", "timestamp"),
    )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POS transaction loader
# ---------------------------------------------------------------------------

# Map POS CSV store_id → API store_id
_POS_STORE_ID_MAP = {
    "ST1008": "STORE_BLR_001",
}


def load_pos_transactions(csv_path: str, db: Session) -> int:
    """
    Load POS transactions from CSV into the database.
    Handles both the problem statement schema and the actual Brigade CSV schema.
    Returns number of records inserted.
    """
    if not os.path.exists(csv_path):
        return 0

    # Pre-load IDs already in the DB to avoid repeated SELECTs
    existing_ids: set[str] = {
        row[0] for row in db.query(POSTransaction.transaction_id).all()
    }
    seen_this_load: set[str] = set()

    inserted = 0
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Support both the problem statement CSV schema and the actual CSV
            if "transaction_id" in row:
                txn_id = row["transaction_id"]
                store_id = _POS_STORE_ID_MAP.get(row.get("store_id", ""), row.get("store_id", ""))
                ts = row.get("timestamp", "")
                basket = float(row.get("basket_value_inr", 0) or 0)
            else:
                # Actual Brigade_Bangalore CSV format
                txn_id = row.get("order_id", "") + "_" + row.get("invoice_number", "")
                raw_store_id = row.get("store_id", "")
                store_id = _POS_STORE_ID_MAP.get(raw_store_id, raw_store_id)
                # Combine date + time into ISO-8601 UTC
                date_str = row.get("order_date", "")  # DD-MM-YYYY
                time_str = row.get("order_time", "00:00:00")
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")
                    ts = dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    ts = _now_iso()
                basket = float(row.get("total_amount", 0) or 0)

            if not txn_id or not store_id:
                continue

            # Skip if already in DB or seen earlier in this file (handles intra-CSV dupes)
            if txn_id in existing_ids or txn_id in seen_this_load:
                continue

            seen_this_load.add(txn_id)
            db.add(POSTransaction(
                transaction_id=txn_id,
                store_id=store_id,
                timestamp=ts,
                basket_value_inr=basket,
            ))
            inserted += 1

    db.commit()
    return inserted
