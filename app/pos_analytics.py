"""
pos_analytics.py — POS revenue and product breakdown.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import csv, os
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import POSAnalyticsResponse, POSHourly, POSProduct, POSCategory

POS_CSV_PATH = os.getenv("POS_CSV_PATH", "Updated-resorces/POS - sample transactionsb1e826f.csv")
_POS_STORE_ID_MAP = {"ST1008": "STORE_BLR_001"}
# Stores that share the CSV sample data — map them to the donor store for CSV lookups
_CSV_DONOR = {"STORE_BLR_002": "STORE_BLR_001"}


def _csv_store(raw: str) -> str:
    return _POS_STORE_ID_MAP.get(raw, raw)


def _effective_store(store_id: str) -> str:
    """Return the store whose CSV rows to read (handles shared demo data)."""
    return _CSV_DONOR.get(store_id, store_id)


def get_pos_analytics(store_id: str, db: Session, date: Optional[str] = None) -> POSAnalyticsResponse:
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # ── totals from DB ─────────────────────────────────────────────────────
    totals = db.execute(text("""
        SELECT
            COUNT(DISTINCT transaction_id) AS txn_count,
            SUM(basket_value_inr)          AS total_revenue,
            AVG(basket_value_inr)          AS avg_basket
        FROM pos_transactions
        WHERE store_id = :store_id
          AND DATE(timestamp) = :date
    """), {"store_id": store_id, "date": date}).fetchone()

    # ── hourly revenue ─────────────────────────────────────────────────────
    hourly_rows = db.execute(text("""
        SELECT CAST(SUBSTR(timestamp,12,2) AS INTEGER) AS hour,
               COUNT(DISTINCT transaction_id) AS txns,
               SUM(basket_value_inr) AS revenue
        FROM pos_transactions
        WHERE store_id = :store_id
          AND DATE(timestamp) = :date
        GROUP BY hour
        ORDER BY hour
    """), {"store_id": store_id, "date": date}).fetchall()

    hourly = [POSHourly(hour=r.hour, transactions=r.txns, revenue=round(r.revenue or 0, 2))
              for r in hourly_rows]

    # ── top products + categories from CSV ────────────────────────────────
    top_products: list[POSProduct] = []
    top_categories: list[POSCategory] = []

    if os.path.exists(POS_CSV_PATH):
        # Aggregate by product_name and dep_name
        prod_map: dict[str, dict] = {}
        cat_map:  dict[str, dict] = {}

        with open(POS_CSV_PATH, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                raw_store = row.get("store_id", "")
                if _csv_store(raw_store) != _effective_store(store_id):
                    continue
                date_str = row.get("order_date", "")
                # DD-MM-YYYY → YYYY-MM-DD
                try:
                    d = datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue
                if d != date:
                    continue

                try:
                    revenue = float(row.get("total_amount", 0) or 0)
                except ValueError:
                    continue

                # Actual CSV has brand_name + product_id but no product_name/dep_name/qty
                brand  = (row.get("brand_name") or "Unknown").strip()
                prod_id = (row.get("product_id") or "").strip()
                # Use "brand · product_id" as the product label when brand is known
                if brand and brand != "Unknown" and prod_id:
                    pname = f"{brand} #{prod_id}"
                elif brand and brand != "Unknown":
                    pname = brand
                else:
                    pname = f"Product {prod_id}" if prod_id else "Unknown"
                pname = pname[:60]

                # Category = brand (most granular grouping available in this CSV)
                cat = brand if brand and brand != "Unknown" else "Other"

                p = prod_map.setdefault(pname, {"product": pname, "brand": brand, "qty": 0, "revenue": 0.0})
                p["qty"] += 1          # each row = 1 line item sold
                p["revenue"] += revenue

                c = cat_map.setdefault(cat, {"category": cat, "sub_category": "", "qty": 0, "revenue": 0.0})
                c["qty"] += 1
                c["revenue"] += revenue

        top_products = [
            POSProduct(product_name=v["product"], brand=v["brand"],
                       qty_sold=v["qty"], revenue=round(v["revenue"], 2))
            for v in sorted(prod_map.values(), key=lambda x: x["revenue"], reverse=True)[:10]
        ]
        top_categories = [
            POSCategory(category=v["category"], sub_category=v["sub_category"],
                        qty_sold=v["qty"], revenue=round(v["revenue"], 2))
            for v in sorted(cat_map.values(), key=lambda x: x["revenue"], reverse=True)[:8]
        ]

    return POSAnalyticsResponse(
        store_id=store_id,
        date=date,
        total_transactions=totals.txn_count or 0,
        total_revenue=round(totals.total_revenue or 0, 2),
        avg_basket_inr=round(totals.avg_basket or 0, 2),
        hourly=hourly,
        top_products=top_products,
        top_categories=top_categories,
    )
