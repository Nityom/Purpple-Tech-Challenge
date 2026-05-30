# DESIGN.md — Store Intelligence System Architecture

## 1. System Overview

The Store Intelligence system transforms raw CCTV footage from Apex Retail's physical stores into real-time, queryable business analytics. It closes the gap between online (fully instrumented) and offline (data blind) channels by applying computer vision and event-driven architecture to produce the same category of metrics that an e-commerce platform produces from clickstreams.

**North Star Metric**: Offline Store Conversion Rate = Visitors who completed a purchase ÷ Total unique visitors in a session window.

---

## 2. Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           STORE INTELLIGENCE PIPELINE                       │
└────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌─────────────────────────────────────────────────┐
  │  CCTV Clips  │────▶│            DETECTION LAYER (pipeline/)           │
  │  (5 × .mp4)  │     │                                                  │
  └──────────────┘     │  ┌─────────────┐   ┌──────────────────────────┐ │
                        │  │ YOLOv8n     │   │  ByteTrack (ultralytics) │ │
  ┌──────────────┐     │  │ Person Det. │──▶│  Multi-object tracking   │ │
  │store_layout  │────▶│  └─────────────┘   └──────────┬───────────────┘ │
  │  .json       │     │                               │                  │
  └──────────────┘     │  ┌────────────────────────────▼─────────────┐   │
                        │  │            Re-ID Module (tracker.py)      │   │
  ┌──────────────┐     │  │  • Appearance fingerprint (colour hist.)  │   │
  │pos_trans.csv │────▶│  │  • Cross-session matching (30-min window) │   │
  └──────────────┘     │  │  • REENTRY detection                      │   │
                        │  └────────────────┬─────────────────────────┘   │
                        │                   │                               │
                        │  ┌────────────────▼─────────────────────────┐   │
                        │  │          Zone Classifier (zones.py)       │   │
                        │  │  • Virtual line crossing → ENTRY/EXIT     │   │
                        │  │  • Polygon ROI matching → ZONE_ENTER/EXIT │   │
                        │  │  • Dwell timer → ZONE_DWELL (every 30s)   │   │
                        │  │  • Queue depth counter → BILLING events   │   │
                        │  │  • Staff heuristic (uniform colour + time)│   │
                        │  └────────────────┬─────────────────────────┘   │
                        │                   │                               │
                        │  ┌────────────────▼─────────────────────────┐   │
                        │  │          Event Emitter (emit.py)          │   │
                        │  │  • Validates schema via Pydantic           │   │
                        │  │  • Writes JSONL to events/output.jsonl    │   │
                        │  │  • POST batches to /events/ingest in RT   │   │
                        │  └────────────────┬─────────────────────────┘   │
                        └───────────────────┼─────────────────────────────┘
                                            │
                                            ▼ structured JSONL events
                        ┌──────────────────────────────────────────────────┐
                        │              INTELLIGENCE API (app/)              │
                        │                                                   │
                        │  POST /events/ingest   ← batch up to 500 events  │
                        │  GET  /stores/{id}/metrics   ← live KPIs         │
                        │  GET  /stores/{id}/funnel    ← conversion funnel  │
                        │  GET  /stores/{id}/heatmap   ← zone frequency    │
                        │  GET  /stores/{id}/anomalies ← real-time alerts  │
                        │  GET  /health                ← system health      │
                        │                                                   │
                        │  ┌──────────────┐    ┌────────────────────────┐  │
                        │  │  SQLite DB   │    │ Structured JSON logger  │  │
                        │  │  (events +   │    │ (trace_id, latency_ms,  │  │
                        │  │   sessions + │    │  store_id, status_code) │  │
                        │  │   POS txns)  │    └────────────────────────┘  │
                        │  └──────────────┘                                │
                        └──────────────────────────────────────────────────┘
                                            │
                                            ▼
                        ┌──────────────────────────────────────────────────┐
                        │             LIVE DASHBOARD (dashboard/)           │
                        │  Rich terminal UI — polls /metrics every 5s      │
                        │  Shows: visitor count, conversion rate, queue     │
                        │  depth, active anomalies — updating in real time  │
                        └──────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Detection Layer (`pipeline/`)

| File | Responsibility |
|------|----------------|
| `detect.py` | Orchestrates per-clip processing: opens video, runs YOLOv8 inference on sampled frames, feeds detections to tracker |
| `tracker.py` | Wraps ByteTrack; maintains per-track Re-ID fingerprints; detects re-entry; classifies staff |
| `zones.py` | Maps normalised bounding box centroids to zone polygons from `store_layout.json`; manages dwell timers and queue depth |
| `emit.py` | Builds Pydantic-validated event payloads; writes to JSONL and optionally POSTs to the API |
| `run.sh` | Single command to process all clips sequentially and feed output to the API |

**Frame sampling strategy**: Process every 3rd frame (5fps effective) to keep CPU/GPU load manageable while maintaining sub-1-second event latency. At 15fps source, a 3-frame step means every detection update is 200ms — adequate for dwell tracking.

**Entry/Exit detection**: A horizontal virtual line is drawn at 60% of frame height. Any tracked person whose bounding-box centroid crosses this line from above → ENTRY; from below → EXIT. Direction is determined by comparing the centroid's y-coordinate across two consecutive frames where it crossed.

**Re-ID strategy**: On each new track, a colour histogram (HSV, 32 bins hue, 16 bins saturation) is extracted from the torso region (middle 40% of bounding box). This fingerprint is stored with the track. When a track terminates (person leaves frame), the fingerprint is cached for 30 minutes per store. Any new track whose cosine similarity to a cached fingerprint exceeds 0.85 is assigned the same `visitor_id` and emits a `REENTRY` event rather than a new `ENTRY`.

**Staff detection**: Two signals combined:
1. Uniform colour: HSV hue in range [90°–130°] (teal) in the torso region (store uniform colour — configurable in `store_layout.json`)  
2. Persistence: track present for ≥60 minutes within one camera view  
Either signal is sufficient to flag `is_staff=true`.

**Cross-camera deduplication**: Tracks active simultaneously in overlapping cameras (entry + floor overlap zone) are deduplicated by matching appearance fingerprints with a 0.80 similarity threshold and suppressing duplicate ZONE_ENTER events within a 5-second window.

### 3.2 Event Stream Schema

Events are emitted as JSONL (one JSON object per line). The schema is defined in `app/models.py` as a Pydantic model and reused by both the pipeline (for validation before emission) and the API (for ingest validation).

Key schema invariants enforced at emission time:
- `event_id` is UUID-v4, globally unique, generated by `uuid.uuid4()`
- `timestamp` is ISO-8601 UTC, derived from clip recording date + frame offset seconds
- `zone_id` is `null` for `ENTRY` and `EXIT` events
- `dwell_ms` is `0` for instantaneous events (`ENTRY`, `EXIT`, `ZONE_ENTER`, `BILLING_QUEUE_JOIN`)
- `confidence` is never suppressed — low-confidence detections are emitted with their actual confidence score
- `session_seq` is a monotonically increasing counter per `visitor_id` session

### 3.3 Intelligence API (`app/`)

**Framework**: FastAPI — chosen for automatic OpenAPI generation, async support, and native Pydantic integration. The scoring harness has best coverage for FastAPI.

**Storage**: SQLite via SQLAlchemy (production path: PostgreSQL, switchable via `DATABASE_URL` env var). SQLite is sufficient for the challenge volume (5 stores × 20min × ~15 events/min ≈ 1,500 events). PostgreSQL becomes necessary above ~50 concurrent stores with real-time ingest.

**Idempotency**: `POST /events/ingest` uses `INSERT OR IGNORE` on the `event_id` unique constraint. The same batch can be sent twice without duplicating data.

**Partial success**: Ingest validates each event individually. Malformed events return a structured error array (`failed_events`) while valid events in the same batch are still committed.

**Session model**: A "visitor session" is defined as all events sharing the same `visitor_id` on the same calendar day for the same `store_id`. Re-entry (same `visitor_id` returning after an EXIT) does not create a new session — it continues the existing session. This is the correct model for funnel deduplication.

**Metrics computation**: All metrics endpoints query the events table directly with SQL aggregations — no pre-computed cache. This ensures real-time accuracy. The one exception is the 7-day historical baseline for anomaly detection, which is re-computed on each anomalies request (acceptable at challenge scale).

**POS correlation**: The `pos_transactions` table is loaded from the CSV at startup (or via a background task). Conversion is determined by checking whether a `visitor_id` had a `BILLING` zone event within the 5-minute window before any POS transaction at the same store. `BILLING_QUEUE_ABANDON` is emitted when a visitor exits the billing zone and no subsequent POS transaction follows within 10 minutes.

### 3.4 Anomaly Detection

Three anomaly types implemented:

| Anomaly | Detection Logic | Severity |
|---------|----------------|----------|
| `BILLING_QUEUE_SPIKE` | `queue_depth > 5` sustained for > 3 minutes | `WARN` if 5–8, `CRITICAL` if > 8 |
| `CONVERSION_DROP` | Today's conversion rate < (7-day avg − 2σ) | `WARN` |
| `DEAD_ZONE` | No `ZONE_ENTER` events for a named zone in > 30 minutes during open hours | `INFO` |
| `STALE_FEED` | No events from a camera in > 10 minutes | `WARN` → `CRITICAL` after 30 min |

Each anomaly includes a `suggested_action` string for on-call engineers.

### 3.5 Live Dashboard (`dashboard/live.py`)

A `rich`-based terminal dashboard that polls `/stores/{id}/metrics` every 5 seconds and renders a live table with: visitor count, conversion rate, zone dwell breakdown, current queue depth, and active anomalies. The refresh rate can be configured. This proves real-time pipeline → API → display connectivity.

---

## 4. Data Flow (End to End)

```
1. pipeline/run.sh invokes detect.py for each CCTV clip
2. detect.py opens video → samples every 3rd frame
3. YOLOv8 detects persons in frame → bounding boxes + confidences
4. ByteTrack assigns/updates track IDs across frames
5. zones.py maps centroid → zone polygon → zone_id
6. tracker.py computes Re-ID fingerprint, checks re-entry cache
7. emit.py constructs StoreEvent (Pydantic), validates, writes to JSONL
8. In real-time mode: emit.py POSTs batches of 50 events to /events/ingest
9. API ingests, deduplicates by event_id, stores in SQLite
10. /metrics, /funnel, /heatmap queries run SQL aggregations on events table
11. dashboard/live.py polls /metrics → renders Rich terminal table
```

---

## 5. Edge Case Handling

| Edge Case | Handling Strategy |
|-----------|------------------|
| Group entry | ByteTrack assigns separate track IDs to each person independently — produces N ENTRY events for N people entering together |
| Staff movement | Uniform colour + long presence heuristic → `is_staff=true`; excluded from all customer metrics queries via `WHERE is_staff = FALSE` |
| Re-entry | Re-ID fingerprint cache (30-min TTL) matches returning visitor → REENTRY event, same `visitor_id`, no new session |
| Partial occlusion | YOLOv8 handles partial occlusion gracefully; ByteTrack uses Kalman filter to predict position during occlusion. Confidence is reported truthfully (not inflated) |
| Billing queue buildup | Person count in `BILLING_QUEUE` polygon = queue depth; updated per processed frame |
| Empty store periods | Zero-traffic periods emit no events — API returns empty metric values with `data_confidence: false` if `session_count < 20`; never crashes or returns null |
| Camera overlap | 5-second deduplication window + appearance fingerprint matching suppresses duplicate ZONE_ENTER from overlapping entry/floor cameras |

---

## 6. AI-Assisted Decisions

### 6.1 Re-ID Strategy — AI suggested deep Re-ID model (OSNet), I chose lighter approach

When designing the Re-ID component, I prompted Claude: *"What are the trade-offs between using a trained Re-ID model (OSNet/torchreid) vs. a colour histogram approach for retail CCTV with face blur applied?"*

The AI response correctly identified that OSNet would give better accuracy but requires a separate GPU-heavy model (~50ms per crop inference), adding significant pipeline latency and complexity. It also noted that face blur (already applied to our footage) removes the most discriminative feature for Re-ID, making even deep models rely heavily on clothing colour — which is exactly what the colour histogram captures.

**I agreed** with the AI's framing of the trade-off and chose the lighter histogram approach. At the challenge scale (1 store, 20-minute clips), the simpler approach performs adequately and is easier to debug. In production at 40 stores I would switch to OSNet.

### 6.2 Database Choice — AI suggested Redis for real-time, I chose SQLite

When designing the event storage layer, I asked Claude: *"For a real-time retail analytics API handling ~15 events/second per store, what storage backend would you choose and why?"*

The AI suggested Redis Streams for the ingest path (high throughput, native TTL) with PostgreSQL for persistence. This is the right production answer. However, for the challenge scope (5 stores, batch + simulated real-time, no horizontal scaling requirement), the added operational complexity of managing two storage systems is not justified.

**I overrode the AI suggestion** and chose SQLite + SQLAlchemy with a `DATABASE_URL` env var to allow a clean PostgreSQL swap. This satisfies `docker compose up` with zero external dependencies while remaining architecturally honest about the production path.

### 6.3 Staff Detection — AI suggested fine-tuned classifier, I chose heuristic

I asked the AI: *"How would you detect store staff in retail CCTV footage where faces are blurred?"*

The AI suggested fine-tuning a binary classifier on labelled staff/customer crops. This would require training data we don't have. It also mentioned a heuristic approach: uniform colour + zone persistence + temporal patterns.

**I agreed with the heuristic approach** as the primary signal, supplemented by the temporal pattern (staff present in all zones throughout the session). Fine-tuning a classifier is noted in CHOICES.md as the production path when labelled data is available.

---

## 7. Production Considerations

- **Scaling**: SQLite → PostgreSQL via `DATABASE_URL`. API is stateless; horizontal scaling with a load balancer requires only shared PostgreSQL.
- **Security**: No PII stored (visitor tokens are anonymous hashes). CSV files are read-only at startup. API has no authentication in the challenge version — in production, API key middleware would be added.
- **Observability**: Every request emits a structured JSON log line with `trace_id`, `store_id`, `endpoint`, `latency_ms`, `status_code`. The `/health` endpoint exposes per-camera last-event timestamps and `STALE_FEED` warnings.
- **Graceful degradation**: All database calls are wrapped in try/except; DB unavailable returns HTTP 503 with structured JSON body. No raw stack traces leak to API consumers.
