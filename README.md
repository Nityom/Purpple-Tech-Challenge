# Store Intelligence — Purplle Tech Challenge

Transforms raw CCTV footage into real-time retail analytics: visitor counting, conversion funnel, zone heatmaps, queue depth, and POS revenue — all surfaced through a REST API and a React web dashboard.

**North Star Metric**: Offline Store Conversion Rate = visitors who reached billing ÷ total unique visitors

---

## Quick Start (Local)

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd store-intelligence

# 2. Create and activate a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install all dependencies
pip install -r requirements.txt -r requirements-pipeline.txt -r requirements-dashboard.txt

# 4. Start the API (auto-seeds DB with POS + events on first run)
bash start.sh --api-only

# 5. Start the web dashboard
cd web && npm install && npm run dev
```

Open **http://localhost:5173** in your browser.

**Flags for `start.sh`**

| Flag | Effect |
|------|--------|
| *(none)* | API + pipeline + terminal dashboard |
| `--api-only` | Start API only |
| `--skip-pipeline` | Start API + terminal dashboard, skip re-running pipeline |

> **Prerequisites**: Python 3.10+, Node.js 18+

---

## Docker (Recommended)

No manual steps beyond cloning. On first start the API auto-seeds both stores with pre-generated events and POS data.

```bash
# Clone
git clone <repo-url> && cd store-intelligence

# Start the API
docker compose up api

# Start API + terminal dashboard
docker compose --profile dashboard up

# Start API + detection pipeline (processes Store 1 footage)
docker compose --profile pipeline up
```

The API is ready at **http://localhost:8000** when you see:
```
store-intelligence-api  | INFO: Application startup complete.
```

Verify with:
```bash
curl http://localhost:8000/health
curl "http://localhost:8000/stores/STORE_BLR_001/metrics?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_002/metrics?date=2026-04-10"
```

Interactive API docs: **http://localhost:8000/docs**

---

## Web Dashboard

React + Vite dashboard (mobile-responsive) auto-polls the API every 10 seconds.

```bash
cd web
npm install
npm run dev
```

Open **http://localhost:5173**

Pages: **Dashboard · Cameras · Analytics · POS Sales**
Store switcher toggles between Purplle Store 1 and Purplle Store 2.
Mobile: bottom navigation bar.

---

## API Endpoints

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/events/ingest` | Ingest up to 500 events (idempotent by `event_id`) |
| `GET` | `/stores/{id}/metrics` | Unique visitors, conversion rate, zone dwell, queue depth |
| `GET` | `/stores/{id}/funnel` | Entry → Zone → Billing → Purchase funnel with drop-off % |
| `GET` | `/stores/{id}/heatmap` | Zone visit frequency, normalised 0–100 |
| `GET` | `/stores/{id}/anomalies` | Active anomalies with severity and suggested action |
| `GET` | `/stores/{id}/cameras` | Per-camera event breakdown (entries, exits, visitors) |
| `GET` | `/stores/{id}/pos` | POS revenue, top products, hourly breakdown |
| `GET` | `/stores/{id}/config` | Camera descriptions, types, zone labels from store_layout.json |
| `GET` | `/health` | Service status and per-store feed freshness |

**Store IDs**: `STORE_BLR_001` (Purplle Store 1) · `STORE_BLR_002` (Purplle Store 2)
**Data date**: `2026-04-10`

```bash
curl "http://localhost:8000/stores/STORE_BLR_001/metrics?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_001/funnel?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_001/heatmap?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_001/anomalies"
curl "http://localhost:8000/stores/STORE_BLR_001/cameras?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_001/pos?date=2026-04-10"
curl "http://localhost:8000/stores/STORE_BLR_001/config"
curl "http://localhost:8000/health"
```

---

## Detection Pipeline

The pipeline runs YOLOv8n + ByteTrack on CCTV footage, classifies zones from `store_layout.json`, and emits structured events.

### Option A — Single clip

```bash
python pipeline/detect.py \
    --video "Updated-resorces/Store 1/CAM 1 - zone.mp4" \
    --store-id STORE_BLR_001 \
    --camera-id CAM_ENTRY_01 \
    --layout store_layout.json \
    --output events/output.jsonl \
    --clip-start 2026-04-10T10:00:00Z \
    --api-url http://localhost:8000
```

### Option B — All clips for a store

```bash
# Store 1
bash pipeline/run.sh --store 1

# Store 2
bash pipeline/run.sh --store 2
```

### Option C — Batch ingest from saved JSONL

```bash
# Ingest pre-generated Store 1 events
python pipeline/ingest_batch.py \
    --events events/output.jsonl \
    --api-url http://localhost:8000 \
    --batch-size 500

# Ingest pre-generated Store 2 events
python pipeline/ingest_batch.py \
    --events events/store2_events.jsonl \
    --api-url http://localhost:8000 \
    --batch-size 500
```

> Pre-generated events (721 per store) are bundled in `events/`. The API auto-ingests them on first start when `SEED_EVENTS_ON_EMPTY=true` (default in Docker).

---

## Terminal Dashboard (bonus)

A `rich`-based live terminal view that polls every 5 seconds:

```bash
python dashboard/live.py --store-id STORE_BLR_001 --api-url http://localhost:8000
```

Displays: visitor count, conversion rate, queue depth, top zone by dwell, active anomalies, and the conversion funnel.

---

## Running Tests

```bash
pip install -r requirements-test.txt

# All tests with coverage
pytest

# Specific suites
pytest tests/test_pipeline.py -v
pytest tests/test_metrics.py -v
pytest tests/test_anomalies.py -v

# HTML coverage report
pytest --cov=app --cov=pipeline --cov-report=html
```

Coverage target: **≥ 70%** statement coverage.

---

## Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8n + ByteTrack detection + zone classification
│   ├── tracker.py         # Re-ID visitor tracking + staff detection
│   ├── zones.py           # Zone classifiers, dwell timers, queue depth
│   ├── emit.py            # Pydantic event schema + JSONL/API emission
│   ├── ingest_batch.py    # Batch ingest helper
│   └── run.sh             # Process all clips for a store (--store 1|2)
├── app/
│   ├── main.py            # FastAPI entrypoint, lifespan, all routes
│   ├── models.py          # Pydantic request/response schemas
│   ├── database.py        # SQLAlchemy + SQLite setup, POS loader
│   ├── ingestion.py       # Idempotent event ingest logic
│   ├── metrics.py         # Visitor, conversion, queue metrics
│   ├── funnel.py          # Conversion funnel computation
│   ├── heatmap.py         # Zone heatmap + dwell aggregation
│   ├── anomalies.py       # Rule-based anomaly detection
│   ├── cameras.py         # Per-camera event breakdown
│   ├── pos_analytics.py   # POS CSV analytics
│   ├── health.py          # Health check + feed freshness
│   └── logger.py          # Structured JSON request logging
├── web/                   # React + Vite dashboard (port 5173)
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       └── components/    # Header, Sidebar, KPIGrid, CameraGrid,
│                          # FunnelChart, HeatmapGrid, POSPanel,
│                          # StoreLayoutMap
├── dashboard/
│   └── live.py            # Rich terminal live dashboard
├── tests/
│   ├── conftest.py
│   ├── test_pipeline.py
│   ├── test_metrics.py
│   └── test_anomalies.py
├── docs/
│   ├── DESIGN.md          # System architecture + AI-Assisted Decisions
│   └── CHOICES.md         # 3 key engineering decisions with full reasoning
├── events/
│   ├── output.jsonl            # 721 pre-generated events — STORE_BLR_001
│   ├── store2_events.jsonl     # 721 pre-generated events — STORE_BLR_002
│   └── sample_events.jsonl     # Sample schema reference
├── Updated-resorces/
│   ├── Store 1/               # CCTV footage + layout for Store 1
│   ├── Store 2/               # CCTV footage + layout for Store 2
│   └── POS - sample transactionsb1e826f.csv
├── store_layout.json           # Zone definitions + camera-to-zone mapping
├── start.sh                    # One-command launcher
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.pipeline
├── requirements.txt
├── requirements-pipeline.txt
├── requirements-dashboard.txt
├── requirements-test.txt
└── pyproject.toml
```

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DATABASE_URL` | `sqlite:////app/db/store_intelligence.db` | Database connection string |
| `POS_CSV_PATH` | `Updated-resorces/POS - sample transactionsb1e826f.csv` | POS transactions CSV |
| `SEED_EVENTS_ON_EMPTY` | `false` (local) / `true` (Docker) | Auto-ingest bundled JSONL on empty DB |
| `API_URL` | *(not set)* | If set, pipeline POSTs events live while processing |
| `FRAME_STEP` | `3` | Process every Nth frame |
| `CLIP_START` | `2026-04-10T10:00:00Z` | Recording start timestamp |

### PostgreSQL

```bash
DATABASE_URL=postgresql://user:password@db:5432/store_intelligence
```

---

## Architecture

```
CCTV Clips
    │
    ▼
YOLOv8n Detection ──► ByteTrack Tracking ──► Re-ID + Zone Classification
                                                         │
                                              POST /events/ingest
                                                         │
                                               SQLite (events table)
                                                         │
                    ┌────────────────────────────────────┼──────────────────┐
                    ▼              ▼            ▼         ▼                  ▼
                /metrics       /funnel      /heatmap  /anomalies          /pos
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
  React Dashboard       Terminal Dashboard
  (port 5173)           (dashboard/live.py)
```

See [docs/DESIGN.md](docs/DESIGN.md) for the full architecture and AI-assisted design decisions.
See [docs/CHOICES.md](docs/CHOICES.md) for the three key engineering decisions with full reasoning.
