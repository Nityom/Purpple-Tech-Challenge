#!/usr/bin/env bash
# run.sh — Process all CCTV clips for Store 1 (Brigade_Bangalore) and feed events to the API.
#
# Usage:
#   ./pipeline/run.sh [--api-url http://localhost:8000] [--frame-step 3] [--store {1,2}]
#
# Prerequisites:
#   pip install -r requirements-pipeline.txt
#   docker compose up -d   (if using API real-time ingest)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LAYOUT="$ROOT_DIR/store_layout.json"
VIDEO_DIR="$ROOT_DIR/Updated-resorces/Store 1"
OUTPUT_DIR="$ROOT_DIR/events"
API_URL="${API_URL:-}"
FRAME_STEP="${FRAME_STEP:-3}"
CLIP_START="${CLIP_START:-2026-04-10T10:00:00Z}"
MODEL="${MODEL:-yolov8n.pt}"
STORE_NUM="${STORE_NUM:-1}"

# Parse CLI overrides
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)   API_URL="$2";   shift 2 ;;
        --frame-step) FRAME_STEP="$2"; shift 2 ;;
        --clip-start) CLIP_START="$2"; shift 2 ;;
        --store)      STORE_NUM="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# Select footage directory and camera mapping based on store
if [[ "$STORE_NUM" == "2" ]]; then
    VIDEO_DIR="$ROOT_DIR/Updated-resorces/Store 2"
    CAM_FILES=("entry 1.mp4" "entry 2.mp4" "zone.mp4" "billing_area.mp4")
    CAM_IDS=(CAM_ENTRY_01 CAM_ENTRY_02 CAM_FLOOR_01 CAM_BILLING_01)
    STORE_IDS=(STORE_BLR_002 STORE_BLR_002 STORE_BLR_002 STORE_BLR_002)
    CAM_STARTS=(
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
    )
else
    CAM_FILES=("CAM 3 - entry.mp4" "CAM 1 - zone.mp4" "CAM 2 - zone.mp4" "CAM 4 - zone.mp4" "CAM 5 - billing.mp4")
    CAM_IDS=(CAM_ENTRY_01 CAM_FLOOR_01 CAM_FLOOR_02 CAM_FLOOR_03 CAM_BILLING_01)
    STORE_IDS=(STORE_BLR_001 STORE_BLR_001 STORE_BLR_001 STORE_BLR_001 STORE_BLR_001)
    CAM_STARTS=(
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
        "2026-04-10T10:00:00Z"
    )
fi

mkdir -p "$OUTPUT_DIR"

OUTPUT_JSONL="$OUTPUT_DIR/output.jsonl"
: > "$OUTPUT_JSONL"   # truncate / create

echo "================================================================"
echo " Store Intelligence Detection Pipeline"
echo " Store:      ${STORE_IDS[0]}"
echo " Video dir:  $VIDEO_DIR"
echo " Output:     $OUTPUT_JSONL"
echo " API URL:    ${API_URL:-<not set — batch mode only>}"
echo " Frame step: $FRAME_STEP"
echo "================================================================"

NUM_CAMS=${#CAM_FILES[@]}
for i in $(seq 0 $((NUM_CAMS - 1))); do
    FILENAME="${CAM_FILES[$i]}"
    CAMERA_ID="${CAM_IDS[$i]}"
    STORE_ID="${STORE_IDS[$i]}"
    CAM_START="${CAM_STARTS[$i]}"

    VIDEO_PATH="$VIDEO_DIR/$FILENAME"
    if [[ ! -f "$VIDEO_PATH" ]]; then
        echo "[run.sh] WARNING: Video not found — skipping: $VIDEO_PATH"
        continue
    fi

    echo ""
    echo "[run.sh] Processing: $FILENAME → $CAMERA_ID"

    API_ARG=""
    [[ -n "$API_URL" ]] && API_ARG="--api-url $API_URL"

    python "$SCRIPT_DIR/detect.py" \
        --video        "$VIDEO_PATH" \
        --store-id     "$STORE_ID" \
        --camera-id    "$CAMERA_ID" \
        --layout       "$LAYOUT" \
        --output       "$OUTPUT_JSONL" \
        --clip-start   "$CAM_START" \
        --frame-step   "$FRAME_STEP" \
        --model        "$MODEL" \
        $API_ARG

    EVENTS_IN_FILE=$(wc -l < "$OUTPUT_JSONL")
    echo "[run.sh] Cumulative events in output: $EVENTS_IN_FILE"
done

echo ""
echo "================================================================"
echo " Pipeline complete."
echo " Events file:  $OUTPUT_JSONL"
echo " Total events: $(wc -l < "$OUTPUT_JSONL")"
echo ""
echo " To ingest into the API manually:"
echo "   python pipeline/ingest_batch.py --events $OUTPUT_JSONL --api-url http://localhost:8000"
echo "================================================================"
