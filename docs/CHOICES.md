# CHOICES.md — Engineering Decision Log

Three major decisions with full reasoning, options considered, AI input, and final choice.

---

## Decision 1: Detection Model Selection

### Problem Statement
Choose a person detection and tracking stack to process 1080p, 15fps CCTV footage with face blur applied, across 5 camera angles, and produce structured events including entry/exit direction, zone transitions, and re-entry detection.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **YOLOv8n + ByteTrack** (chosen) | Single pip install (ultralytics); ByteTrack built-in; excellent person detection; fast enough on CPU for 5fps effective; well-documented edge case handling | Not state-of-the-art for small/occluded persons |
| **YOLOv9 / RT-DETR** | Marginally better mAP on benchmarks | Heavier; no ByteTrack built-in; more setup complexity |
| **MediaPipe Pose** | Very fast; good for single-person | Degrades significantly with groups; not designed for crowd counting |
| **Detectron2 (Mask R-CNN)** | High accuracy, good occlusion handling | Slow without high-end GPU; complex setup; overkill for person detection alone |
| **ByteTrack with custom detector** | Flexible detector choice | Requires separate integration work; adds complexity without clear gain |

### What AI Suggested

Prompted Claude: *"For retail CCTV analytics — person detection, tracking, and Re-ID — what model stack would you recommend given faces are blurred and we need to run on commodity hardware (CPU or single consumer GPU)?"*

AI recommended YOLOv8 + ByteTrack as the pragmatic choice, but also flagged RT-DETR as worth considering if detection accuracy on occluded persons was the primary concern. It specifically noted that YOLOv8's COCO training includes many crowded-scene images, which is directly relevant to group entry and billing queue scenarios.

### What I Chose and Why

**YOLOv8n (nano variant) + ByteTrack via ultralytics.**

The `ultralytics` library bundles YOLOv8 detection with ByteTrack tracking in a single API call (`model.track()`), which eliminates integration risk. The nano model runs at ~30fps on CPU for 720p input, meaning I can downsample the 1080p clips to 720p and process every 3rd frame (5fps effective) while still maintaining sub-200ms detection latency per frame. This is fast enough for dwell tracking (30-second granularity) and entry/exit counting.

**Why not YOLOv9 or RT-DETR**: The marginal accuracy gain (3–5% mAP on benchmarks) does not justify the additional setup complexity and lack of built-in ByteTrack integration. The challenge evaluates engineering judgment, not benchmark scores.

**Frame sampling decision (every 3rd frame)**: At 15fps, skipping 2 frames means a person walking at normal retail pace (~1.2 m/s) moves approximately 8cm per sampled frame. This is well within ByteTrack's Kalman filter prediction range and causes no track loss. Dwell timers are accumulated in wall-clock time (not frame count), so sub-sampling does not affect dwell accuracy.

**Re-ID approach**: Colour histogram (HSV) over a trained Re-ID model (OSNet/torchreid). Rationale: face blur removes the most discriminative feature for Re-ID. In a retail setting with face blur, deep Re-ID models primarily learn clothing colour and texture — which a well-designed histogram captures with much lower latency. The histogram approach runs in <1ms per crop vs ~50ms for OSNet inference, keeping the pipeline real-time capable on CPU.

---

## Decision 2: Event Schema Design

### Problem Statement
Design a structured event schema that supports: entry/exit counting, dwell analysis, zone-level behaviour, billing queue tracking, re-entry detection, POS correlation, staff exclusion, and all downstream API queries.

### Options Considered

**Option A — Fine-grained event stream (chosen)**  
One JSON event per meaningful state transition per visitor. Each event is self-contained — carries enough context (`store_id`, `camera_id`, `visitor_id`, `zone_id`, `is_staff`) to be processed independently.

**Option B — Aggregated session records**  
Emit one record per visitor session at session close (EXIT event). Simpler downstream, but loses temporal granularity. The /funnel and /heatmap endpoints require zone-level timing that aggregated records cannot provide.

**Option C — Raw detection stream**  
Emit one event per frame per detected person. Fine-grained but very high volume (~15fps × N persons). The downstream API would need to do all aggregation, increasing query complexity. Also, the problem statement explicitly calls for behavioural events (ENTRY, ZONE_DWELL, etc.) not raw detections.

### What AI Suggested

Asked Claude: *"Design a minimal but sufficient event schema for retail store analytics supporting: visitor counting, conversion funnel, zone dwell, re-entry detection, and POS correlation."*

AI suggested the schema very close to what the problem statement specifies, with two additions it recommended:
1. A `session_id` field (separate from `visitor_id`) to distinguish re-entries as new sessions
2. A `bbox` field (normalised bounding box coordinates) for spatial analysis

**On session_id**: I considered this carefully. The problem statement uses `visitor_id` as the session token ("unique per visit session") but also requires REENTRY to reuse the same `visitor_id`. I resolved this by defining a session as `visitor_id + date` in the API layer rather than adding a separate field to the event schema. This keeps the schema minimal while preserving the ability to distinguish sessions.

**On bbox**: I chose not to include this. The downstream API endpoints (metrics, funnel, heatmap) do not require spatial coordinates — zone assignment happens in the pipeline and is encoded in `zone_id`. Storing bbox data would increase event payload size by ~20% with no API-layer benefit.

### What I Chose and Why

The schema specified in the problem statement, with the `session_seq` field in metadata as the ordinal counter. Key design rationale:

- **`event_id` as UUID-v4**: Globally unique, enables idempotent ingest without coordination
- **`is_staff` as top-level field (not in metadata)**: Staff exclusion is a filter on every customer-facing query — keeping it top-level enables efficient SQL indexing
- **`confidence` always present**: Low-confidence events are never suppressed. The API layer can filter by confidence threshold if needed; the pipeline layer should not make that decision
- **`dwell_ms` as integer milliseconds**: Avoids floating-point comparison issues; integers are more compact in JSON and SQL
- **`zone_id: null` for ENTRY/EXIT**: These events happen at the entry threshold, which is not a product zone. Forcing a zone assignment would create ambiguity

---

## Decision 3: API Architecture — Storage and Real-Time Computation

### Problem Statement
Choose a storage backend and query strategy for the Intelligence API that satisfies: real-time metrics (not cached from yesterday), idempotent ingest, session deduplication, 7-day historical baseline for anomaly detection, and zero-dependency `docker compose up`.

### Options Considered

| Option | Real-Time | Complexity | Docker | Notes |
|--------|-----------|------------|--------|-------|
| **SQLite + SQLAlchemy** (chosen) | ✓ (on-demand queries) | Low | Zero deps | Single file DB; no extra container |
| **PostgreSQL + SQLAlchemy** | ✓ | Medium | Requires DB container | Production-ready; JSONB support |
| **Redis (ingest) + PostgreSQL (persist)** | ✓✓ | High | Two extra containers | Ideal for 40+ live stores |
| **ClickHouse** | ✓ (columnar analytics) | High | Extra container | Over-engineered for challenge scale |
| **DuckDB** | ✓ | Low | Zero deps | Excellent analytical queries; no concurrent writes |

### What AI Suggested

Prompted: *"For a REST API that needs: idempotent event ingest at ~15 events/second per store, real-time aggregation queries, and anomaly detection against 7-day history — what storage architecture would you choose?"*

AI recommended **PostgreSQL with materialised views** refreshed every 30 seconds for the aggregation-heavy endpoints (metrics, funnel, heatmap). It argued this is the right production approach because:
- Materialised views pre-compute expensive aggregations
- PostgreSQL's `ON CONFLICT DO NOTHING` handles idempotency natively
- Horizontal scaling is straightforward

**I agreed with the PostgreSQL path for production but overrode it for the challenge.** The challenge constraint is `docker compose up` with no manual steps beyond `git clone`. Adding a PostgreSQL container increases startup complexity (health checks, migration scripts, connection retry logic) and makes local development harder. The requirement for "real-time — not cached from yesterday" means materialised views (which introduce a refresh lag) are actually wrong for the `/metrics` endpoint. On-demand SQL queries over SQLite are both real-time and zero-dependency.

### What I Chose and Why

**SQLite as the default, PostgreSQL as the production path switchable via `DATABASE_URL` environment variable.**

The API uses SQLAlchemy's abstraction layer throughout — no raw SQL dialect differences. Switching from SQLite to PostgreSQL requires only changing `DATABASE_URL` in `docker-compose.yml`. This is documented in the README.

**Why not DuckDB**: DuckDB is excellent for analytical queries but does not support concurrent writes from multiple processes. The detection pipeline and the API may ingest events simultaneously in real-time mode, which requires write concurrency. SQLite handles this with WAL mode.

**Query strategy for metrics**: All `/metrics`, `/funnel`, and `/heatmap` endpoints run SQL aggregations directly against the `events` table. No caching layer. At the challenge scale, these queries complete in <50ms. The `/anomalies` endpoint runs a slightly heavier 7-day window query — still <200ms on the challenge dataset. I added SQLite indexes on `(store_id, timestamp)` and `(visitor_id, store_id)` to keep these queries fast as data grows.

**Session deduplication implementation**: The `/funnel` endpoint groups by `visitor_id` + `DATE(timestamp)` to produce unique sessions. Re-entries (same `visitor_id`, multiple `ENTRY` events on the same day) are treated as one session because the funnel measures unique visitors who completed each stage, not raw event counts. This matches the business intent: a customer who re-enters and makes a purchase counts as one converted visitor.

---

## Bonus: VLM Usage for Zone Classification

I evaluated using GPT-4V (via OpenAI API) for zone classification — specifically to automatically identify which frame regions correspond to which product zones by analysing a sample frame from each camera.

**Prompt used**: *"Here is a frame from a retail store CCTV camera. The store sells skincare, makeup, hair care, and bath & body products. Identify the approximate bounding regions (as normalised 0-1 coordinates) for each product zone visible in this frame. Return JSON."*

**Result**: GPT-4V produced plausible zone boundaries for the skincare/makeup distinction based on shelf height and product colour patterns. However, the boundaries varied significantly across different sample frames from the same camera (lighting changes, customers blocking shelves), making automated zone polygon extraction unreliable without additional spatial smoothing.

**Decision**: I chose rule-based zone polygons defined manually in `store_layout.json` (configurable per camera). The manual approach is more reliable and reproducible. The VLM experiment is valuable as a future path — with 50+ sample frames averaged, the VLM-derived boundaries would be worth using as a starting point for manual refinement. I would revisit this decision for a production deployment where a store layout expert is not available to define polygons.
