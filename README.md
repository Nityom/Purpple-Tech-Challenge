# Store Intelligence — Apex Retail

A complete pipeline that transforms raw CCTV footage into real-time store analytics: visitor counting, conversion funnel, zone heatmaps, and anomaly detection.

**North Star Metric**: Offline Store Conversion Rate = visitors who purchased ÷ total unique visitors

---

## Quick Start (5 commands)

```bash
# 1. Clone the repository
git clone <repo-url> && cd store-intelligence

# 2. Create a virtual environment and install all dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-pipeline.txt -r requirements-dashboard.txt

# 3. Start the API
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 4. Run the detection pipeline on all CCTV clips
API_URL=http://localhost:8000 bash pipeline/run.sh

# 5. Query live metrics
curl http://localhost:8000/stores/STORE_BLR_001/metrics
```

> **Prerequisites**: Python 3.10+. Docker is optional (see [Docker section](#docker-optional) below).

---

## Running the Detection Pipeline

### Option A — Docker (recommended for production)

```bash
# Build the pipeline container (downloads YOLOv8 model ~6MB)
docker build -f Dockerfile.pipeline -t store-pipeline .

# Process a single clip
docker run --rm \
  -v "$(pwd)/CCTV Footage:/clips" \
  -v "$(pwd)/events:/app/events" \
  store-pipeline \
    --video "/clips/CAM 1.mp4" \
    --store-id STORE_BLR_001 \
    --camera-id CAM_ENTRY_01 \
    --layout /app/store_layout.json \
    --output /app/events/output.jsonl \
    --clip-start 2026-04-10T10:00:00Z \
    --api-url http://host.docker.internal:8000
```

### Option B — Local Python

```bash
# Install pipeline dependencies
pip install -r requirements-pipeline.txt

# Process all 5 clips sequentially and feed events to the API in real time
API_URL=http://localhost:8000 bash pipeline/run.sh

# Or process a single clip
python pipeline/detect.py \
    --video "CCTV Footage/CAM 1.mp4" \
    --store-id STORE_BLR_001 \
    --camera-id CAM_ENTRY_01 \
    --layout store_layout.json \
    --output events/output.jsonl \
    --clip-start 2026-04-10T10:00:00Z \
    --api-url http://localhost:8000
```

### Option C — Batch ingest (post-processing)

```bash
# Run pipeline without API (saves to JSONL)
bash pipeline/run.sh

# Then ingest the JSONL file into the API
python pipeline/ingest_batch.py \
    --events events/output.jsonl \
    --api-url http://localhost:8000 \
    --batch-size 500
```

**Events output location**: `events/output.jsonl`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/events/ingest` | Ingest up to 500 events (idempotent by `event_id`) |
| `GET` | `/stores/{id}/metrics` | Unique visitors, conversion rate, zone dwell, queue depth |
| `GET` | `/stores/{id}/funnel` | Entry → Zone → Billing → Purchase funnel with drop-off % |
| `GET` | `/stores/{id}/heatmap` | Zone visit frequency, normalised 0–100 |
| `GET` | `/stores/{id}/anomalies` | Active anomalies with severity and suggested action |
| `GET` | `/health` | Service status and per-store feed freshness |

**Example store ID**: `STORE_BLR_001` (Brigade Road, Bangalore)

```bash
# Metrics
curl http://localhost:8000/stores/STORE_BLR_001/metrics

# Funnel
curl http://localhost:8000/stores/STORE_BLR_001/funnel

# Heatmap
curl http://localhost:8000/stores/STORE_BLR_001/heatmap

# Anomalies
curl http://localhost:8000/stores/STORE_BLR_001/anomalies
```

Auto-generated API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Live Dashboard (Part E — bonus)

The terminal dashboard polls the API every 5 seconds and displays live metrics:

```bash
# Install dashboard dependencies
pip install -r requirements-dashboard.txt

# Start the dashboard (API must be running)
python dashboard/live.py --store-id STORE_BLR_001 --api-url http://localhost:8000
```

Or with Docker Compose (includes dashboard):

```bash
docker compose --profile dashboard up
```

The dashboard shows: visitor count, conversion rate, queue depth, top zone by dwell, active anomalies, and the conversion funnel — all updating every 5 seconds.

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests with coverage
pytest

# Run specific test files
pytest tests/test_pipeline.py -v
pytest tests/test_metrics.py -v
pytest tests/test_anomalies.py -v

# Check coverage only
pytest --cov=app --cov=pipeline --cov-report=html
```

Coverage target: **>70%** statement coverage. Edge cases covered: empty store, all-staff clip, zero purchases, re-entry in funnel.

---

## Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8 + ByteTrack detection + zone classification
│   ├── tracker.py         # Re-ID visitor tracking + staff detection
│   ├── zones.py           # Zone classifiers, dwell timers, queue depth
│   ├── emit.py            # Pydantic event schema + JSONL/API emission
│   ├── ingest_batch.py    # Batch ingest helper
│   └── run.sh             # Process all clips → events
├── app/
│   ├── main.py            # FastAPI entrypoint
│   ├── models.py          # Pydantic schemas
│   ├── database.py        # SQLAlchemy + SQLite/PostgreSQL setup
│   ├── ingestion.py       # Idempotent event ingest
│   ├── metrics.py         # Real-time metric computation
│   ├── funnel.py          # Conversion funnel logic
│   ├── heatmap.py         # Zone heatmap computation
│   ├── anomalies.py       # Anomaly detection
│   ├── health.py          # Health endpoint
│   └── logger.py          # Structured JSON request logging
├── dashboard/
│   └── live.py            # Rich terminal live dashboard
├── tests/
│   ├── conftest.py
│   ├── test_pipeline.py   # Pipeline unit tests
│   ├── test_metrics.py    # API integration tests
│   └── test_anomalies.py  # Anomaly detection tests
├── docs/
│   ├── DESIGN.md          # Architecture + AI-Assisted Decisions
│   └── CHOICES.md         # 3 key decisions with full reasoning
├── CCTV Footage/          # Input: CAM 1–5.mp4
├── events/                # Output: output.jsonl (generated by pipeline)
├── store_layout.json      # Zone definitions and camera config
├── Brigade_Bangalore_10_April_26 (1)bc6219c.csv  # POS transactions
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
| `DATABASE_URL` | `sqlite:///./store_intelligence.db` | Database connection string |
| `POS_CSV_PATH` | `Brigade_Bangalore_10_April_26 (1)bc6219c.csv` | Path to POS transactions CSV |
| `API_URL` | *(not set)* | If set, pipeline POSTs events in real time |
| `FRAME_STEP` | `3` | Process every Nth frame (lower = slower, more accurate) |
| `CLIP_START` | `2026-04-10T10:00:00Z` | Recording start timestamp for the clips |

### Switching to PostgreSQL

```bash
# In docker-compose.yml, change DATABASE_URL to:
DATABASE_URL=postgresql://user:password@db:5432/store_intelligence
```

---

## Architecture Summary

```
CCTV Clips → YOLOv8n Detection → ByteTrack Tracking → Re-ID → Zone Events
                                                                      ↓
                                                       /events/ingest (POST)
                                                                      ↓
                                                         SQLite (events table)
                                                                      ↓
                          /metrics  /funnel  /heatmap  /anomalies  /health
                                                                      ↓
                                                         Rich Terminal Dashboard
```

See [docs/DESIGN.md](docs/DESIGN.md) for the full architecture and AI-assisted design decisions.  
See [docs/CHOICES.md](docs/CHOICES.md) for the three key engineering decisions with full reasoning.
