"""
ingest_batch.py — Reads a JSONL events file and POSTs batches to /events/ingest.

Usage:
    python pipeline/ingest_batch.py \\
        --events events/output.jsonl \\
        --api-url http://localhost:8000 \\
        [--batch-size 500] \\
        [--simulated-realtime]  # adds wall-clock delay between batches
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx


def ingest_batch(api_url: str, events: list[dict], timeout: float = 30.0) -> dict:
    url = f"{api_url.rstrip('/')}/events/ingest"
    resp = httpx.post(url, json={"events": events}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingest JSONL events into the API")
    parser.add_argument("--events", required=True, help="Path to JSONL events file")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--batch-size", type=int, default=500, help="Events per batch")
    parser.add_argument(
        "--simulated-realtime",
        action="store_true",
        help="Add a small delay between batches to simulate streaming",
    )
    args = parser.parse_args()

    with open(args.events, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    total = len(lines)
    print(f"[ingest_batch] Ingesting {total} events in batches of {args.batch_size}")

    ingested = 0
    failed = 0

    for i in range(0, total, args.batch_size):
        batch_lines = lines[i : i + args.batch_size]
        events = []
        for line in batch_lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[ingest_batch] Skipping malformed line: {e}", file=sys.stderr)
                failed += 1
                continue

        if not events:
            continue

        try:
            result = ingest_batch(args.api_url, events)
            ingested += result.get("ingested_count", len(events))
            if result.get("failed_events"):
                failed += len(result["failed_events"])
                for fe in result["failed_events"][:3]:
                    print(f"[ingest_batch] Failed event: {fe}", file=sys.stderr)
        except Exception as e:
            print(f"[ingest_batch] ERROR posting batch {i//args.batch_size + 1}: {e}",
                  file=sys.stderr)
            failed += len(events)

        pct = min(100.0, (i + len(batch_lines)) / total * 100)
        print(f"[ingest_batch] {pct:.1f}% — ingested={ingested} failed={failed}")

        if args.simulated_realtime:
            time.sleep(0.1)

    print(f"\n[ingest_batch] Done. ingested={ingested} failed={failed}")


if __name__ == "__main__":
    main()
