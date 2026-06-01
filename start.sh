#!/usr/bin/env bash
# start.sh — One-command launcher for Store Intelligence.
#
# Usage:
#   bash start.sh               # start API + run pipeline + open dashboard
#   bash start.sh --api-only    # start API only (skip pipeline + dashboard)
#   bash start.sh --skip-pipeline  # start API + dashboard, skip re-running pipeline
#
# The API runs in the background; the dashboard runs in the foreground.
# Press Ctrl+C to stop the dashboard (API keeps running).
# To stop the API: kill $(cat .api.pid)

set -euo pipefail

VENV=".venv/bin"
API_URL="http://localhost:8000"
STORE_ID="STORE_BLR_001"
DATE="2026-04-10"   # footage date — change to "today" to use current date

API_ONLY=false
SKIP_PIPELINE=false
for arg in "$@"; do
    case $arg in
        --api-only)       API_ONLY=true ;;
        --skip-pipeline)  SKIP_PIPELINE=true ;;
    esac
done

# ── 0. Check venv ────────────────────────────────────────────────────────────
if [[ ! -f "$VENV/python" ]]; then
    echo "[start.sh] Creating virtual environment..."
    python3 -m venv .venv
    "$VENV/pip" install -q -r requirements.txt -r requirements-pipeline.txt -r requirements-dashboard.txt
    echo "[start.sh] Dependencies installed."
fi

# ── 1. Stop any existing API on port 8000 ────────────────────────────────────
if lsof -ti tcp:8000 &>/dev/null; then
    echo "[start.sh] Stopping existing process on port 8000..."
    kill "$(lsof -ti tcp:8000)" 2>/dev/null || true
    sleep 1
fi

# ── 2. Start API ─────────────────────────────────────────────────────────────
echo "[start.sh] Starting API (logs → api.log)..."
"$VENV/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --log-level warning >"api.log" 2>&1 &
API_PID=$!
echo $API_PID > .api.pid

# Wait for API to be ready
for i in $(seq 1 10); do
    if curl -sf "$API_URL/health" >/dev/null 2>&1; then
        echo "[start.sh] API ready at $API_URL  (PID $API_PID)"
        break
    fi
    sleep 1
done

if $API_ONLY; then
    echo "[start.sh] API running. Docs: $API_URL/docs"
    echo "[start.sh] Stop with: kill \$(cat .api.pid)"
    exit 0
fi

# ── 3. Run pipeline ───────────────────────────────────────────────────────────
if ! $SKIP_PIPELINE; then
    echo ""
    echo "[start.sh] Running detection pipeline (all 5 clips)..."
    API_URL="$API_URL" PATH="$VENV:$PATH" bash pipeline/run.sh
fi

# ── 4. Show summary ──────────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo " Results for $STORE_ID on $DATE"
echo "================================================================"
curl -s "$API_URL/stores/$STORE_ID/metrics?date=$DATE" | "$VENV/python" -m json.tool
echo ""
curl -s "$API_URL/stores/$STORE_ID/heatmap?date=$DATE" | "$VENV/python" -m json.tool

# ── 5. Launch dashboard ──────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo " Quick Links"
echo "================================================================"
echo " Web Dashboard  →  http://localhost:5175  (cd web && npm run dev)"
echo " API Docs       →  $API_URL/docs"
echo " Stop API       →  kill \$(cat .api.pid)"
echo "================================================================"
echo ""
echo "[start.sh] Launching terminal dashboard (Ctrl+C to stop, API keeps running)..."
"$VENV/python" dashboard/live.py \
    --store-id "$STORE_ID" \
    --api-url  "$API_URL" \
    --date     "$DATE"
