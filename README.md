# Store Intelligence — Purpple Tech Challenge

Transforms raw CCTV footage into real-time retail analytics: visitor counting, conversion funnel, zone heatmaps, queue depth, and anomaly detection — all surfaced through a REST API and a React web dashboard.

**North Star Metric**: Offline Store Conversion Rate = unique purchasers ÷ unique visitors

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install all dependencies
pip install -r requirements.txt -r requirements-pipeline.txt -r requirements-dashboard.txt

# 3. One command — starts API, runs pipeline on all 5 clips, shows metrics summary,
#    then launches the terminal dashboard
bash start.sh
```

**Flags**

| Flag | Effect |
|------|--------|
| *(none)* | API + pipeline + terminal dashboard |
| `--api-only` | Start API only, skip pipeline and dashboard |
| `--skip-pipeline` | Start API + dashboard, skip re-running the pipeline |

> **Prerequisites**: Python 3.10+, Node.js 18+ (for the web dashboard). Docker is optional.

---

## Web Dashboard

A React + Vite dashboard (mobile-responsive) runs separately from the terminal dashboard:

```bash
cd web
npm install
npm run dev
```

Open **http://localhost:5175** in your browser.

Pages: Dashboard · Cameras · Analytics · POS Sales · Anomalies  
Auto-polls the API every 10 seconds. Works on mobile via bottom navigation.

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
| `GET` | `/health` | Service status and per-store feed freshness |

**Example store ID**: `STORE_BLR_001` — Brigade Road, Bangalore, 2026-04-10

```bash
curl http://localhost:8000/stores/STORE_BLR_001/metrics?date=2026-04-10
curl http://localhost:8000/stores/STORE_BLR_001/funnel?date=2026-04-10
curl http://localhost:8000/stores/STORE_BLR_001/heatmap?date=2026-04-10
curl http://localhost:8000/stores/STORE_BLR_001/anomalies
curl http://localhost:8000/stores/STORE_BLR_001/cameras?date=2026-04-10
curl http://localhost:8000/stores/STORE_BLR_001/pos?date=2026-04-10
curl http://localhost:8000/health
```

Interactive API docs: **http://localhost:8000/docs**

---

## Detection Pipeline

### Option A — One command (recommended)

```bash
bash start.sh
```

Runs all 5 clips sequentially, streams events to the API in real time, then prints a metrics summary.

### Option B — Single clip

```bash
python pipeline/detect.py \
    --video "CCTV Footage/CAM 1.mp4" \
    --store-id STORE_BLR_001 \
    --camera-id CAM_ENTRY_01 \
    --layout store_layout.json \
    --output events/output.jsonl \
    --clip-start 2026-04-10T10:00:00Z \
    --api-url http://localhost:8000
```

### Option C — Batch ingest from saved JSONL

```bash
# Run pipeline without live API (saves events to JSONL)
bash pipeline/run.sh

# Then bulk-ingest the file
python pipeline/ingest_batch.py \
    --events events/output.jsonl \
    --api-url http://localhost:8000 \
    --batch-size 500
```

### Docker

```bash
# API only
docker compose up api

# API + pipeline
docker compose up

# Build pipeline image manually
docker build -f Dockerfile.pipeline -t store-pipeline .
docker run --rm \
  -v "$(pwd)/CCTV Footage:/clips" \
  -v "$(pwd)/events:/app/events" \
  store-pipeline \
    --video "/clips/CAM 1.mp4" \
    --store-id STORE_BLR_001 \
    --camera-id CAM_ENTRY_01 \
    --api-url http://host.docker.internal:8000
```

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
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests with coverage report
pytest

# Run specific suites
pytest tests/test_pipeline.py -v
pytest tests/test_metrics.py -v
pytest tests/test_anomalies.py -v

# HTML coverage report
pytest --cov=app --cov=pipeline --cov-report=html
```

Coverage target: **≥70%** statement coverage. Test suite: 69 tests across pipeline unit tests, API integration tests, and anomaly detection tests.

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
│   └── run.sh             # Process all 5 clips sequentially
├── app/
│   ├── main.py            # FastAPI entrypoint + router registration
│   ├── models.py          # Pydantic request/response schemas
│   ├── database.py        # SQLAlchemy + SQLite setup
│   ├── ingestion.py       # Idempotent event ingest logic
│   ├── metrics.py         # Visitor, conversion, queue metrics
│   ├── funnel.py          # Conversion funnel computation
│   ├── heatmap.py         # Zone heatmap + dwell aggregation
│   ├── anomalies.py       # Rule-based anomaly detection
│   ├── cameras.py         # Per-camera event breakdown
│   ├── pos_analytics.py   # POS CSV analytics
│   ├── health.py          # Health check + feed freshness
│   └── logger.py          # Structured JSON request logging
├── web/                   # React + Vite dashboard (port 5175)
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       └── components/    # Header, Sidebar, KPIGrid, CameraGrid,
│                          # FunnelChart, HeatmapGrid, POSPanel, AnomalyList
├── dashboard/
│   └── live.py            # Rich terminal live dashboard
├── tests/
│   ├── conftest.py
│   ├── test_pipeline.py   # Pipeline unit tests (33 tests)
│   ├── test_metrics.py    # API integration tests
│   └── test_anomalies.py  # Anomaly detection tests
├── docs/
│   ├── DESIGN.md          # System architecture + AI-Assisted Decisions
│   └── CHOICES.md         # 3 key engineering decisions with full reasoning
├── CCTV Footage/          # Input: CAM 1–5.mp4
├── events/                # Output: output.jsonl (523 events, generated by pipeline)
├── store_layout.json      # Zone definitions and camera-to-zone mapping
├── Brigade_Bangalore_10_April_26 (1)bc6219c.csv  # POS transactions
├── start.sh               # One-command launcher
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.pipeline
├── requirements.txt            # API dependencies
├── requirements-pipeline.txt   # Pipeline dependencies (YOLOv8, OpenCV)
├── requirements-dashboard.txt  # Terminal dashboard (rich)
├── requirements-test.txt       # Test dependencies
└── pyproject.toml              # pytest config (testpaths, pythonpath, coverage)
```

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./store_intelligence.db` | Database connection string |
| `POS_CSV_PATH` | `Brigade_Bangalore_10_April_26 (1)bc6219c.csv` | POS transactions CSV |
| `API_URL` | *(not set)* | If set, pipeline POSTs events live while processing |
| `FRAME_STEP` | `3` | Process every Nth frame (lower = slower, higher accuracy) |
| `CLIP_START` | `2026-04-10T10:00:00Z` | Recording start timestamp for footage |

### PostgreSQL

Change `DATABASE_URL` in `docker-compose.yml`:

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
                                                  SQLite (events)
                                                         │
                          ┌──────────────────────────────┼──────────────────┐
                          ▼              ▼               ▼                  ▼
                      /metrics       /funnel         /heatmap          /anomalies
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
        React Dashboard      Terminal Dashboard
        (port 5175)          (dashboard/live.py)
```

See [docs/DESIGN.md](docs/DESIGN.md) for the full architecture and AI-assisted design decisions.  
See [docs/CHOICES.md](docs/CHOICES.md) for the three key engineering decisions with full reasoning.


