"""
detect.py — Main detection and tracking script.

Processes a single CCTV video clip through the full pipeline:
  1. YOLOv8n person detection (via ultralytics)
  2. ByteTrack multi-object tracking (built into ultralytics)
  3. Zone classification (zones.py)
  4. Re-ID and visitor session management (tracker.py)
  5. Event emission to JSONL + optional API POST (emit.py)

Usage:
    python detect.py --video "CCTV Footage/CAM 1.mp4" \\
                     --store-id STORE_BLR_001 \\
                     --camera-id CAM_ENTRY_01 \\
                     --layout store_layout.json \\
                     --output events/output.jsonl \\
                     --clip-start 2026-04-10T10:00:00Z \\
                     [--api-url http://localhost:8000] \\
                     [--frame-step 3]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2

# Pipeline modules
from emit import EventEmitter, build_event, frame_to_timestamp
from tracker import VisitorTracker
from zones import (
    DwellTracker,
    LineCrossingDetector,
    QueueDepthTracker,
    ZoneClassifier,
)

# ---------------------------------------------------------------------------
# ultralytics import (YOLOv8 + ByteTrack)
# ---------------------------------------------------------------------------
try:
    from ultralytics import YOLO
except ImportError:
    print("ERROR: ultralytics not installed. Run: pip install ultralytics", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Camera type constants
# ---------------------------------------------------------------------------
CAM_TYPE_ENTRY_EXIT = "entry_exit"
CAM_TYPE_FLOOR = "floor"
CAM_TYPE_BILLING = "billing"

BILLING_ZONE_IDS = {"BILLING", "BILLING_QUEUE"}

# Deduplication window: suppress duplicate ZONE_ENTER for same visitor within N seconds
CROSS_CAM_DEDUP_WINDOW = 5.0


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

def process_clip(
    video_path: str,
    store_id: str,
    camera_id: str,
    camera_type: str,
    layout: dict,
    roi_polygons: dict,
    entry_line_pos: Optional[float],
    clip_start_iso: str,
    output_path: str,
    api_url: Optional[str],
    frame_step: int = 3,
    model_name: str = "yolov8n.pt",
) -> int:
    """
    Process one video clip end-to-end.
    Returns the number of events emitted.
    """
    model = YOLO(model_name)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}", file=sys.stderr)
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[detect] {video_path} | fps={fps:.1f} | frames={total_frames} | step={frame_step}")

    emitter = EventEmitter(output_path=output_path, api_url=api_url)
    visitor_tracker = VisitorTracker()
    zone_classifier = ZoneClassifier(roi_polygons)
    dwell_tracker = DwellTracker()
    queue_tracker = QueueDepthTracker(BILLING_ZONE_IDS)

    line_detector: Optional[LineCrossingDetector] = None
    if camera_type == CAM_TYPE_ENTRY_EXIT and entry_line_pos is not None:
        line_detector = LineCrossingDetector(position=entry_line_pos)

    # Track which track IDs were active in the previous processed frame
    prev_track_ids: set[int] = set()

    # Dedup cache: (visitor_id, zone_id) → last_emit_monotonic_time
    zone_enter_dedup: dict[tuple[str, str], float] = {}

    frame_index = 0
    events_emitted = 0

    store_sku_zones = {
        zone_name: zone_data.get("sku_zone")
        for zone_name, zone_data in layout.get("zones", {}).items()
    }

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_index += 1
            if frame_index % frame_step != 0:
                continue

            h_frame, w_frame = frame.shape[:2]
            now_mono = time.monotonic()
            timestamp = frame_to_timestamp(clip_start_iso, frame_index, fps)

            # -----------------------------------------------------------
            # Run YOLOv8 tracking (person class = 0 in COCO)
            # -----------------------------------------------------------
            results = model.track(
                frame,
                classes=[0],   # person only
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                conf=0.35,
                iou=0.45,
            )

            current_track_ids: set[int] = set()

            if results and results[0].boxes is not None:
                boxes = results[0].boxes
                ids = boxes.id
                if ids is not None:
                    for i, track_id in enumerate(ids.int().tolist()):
                        xyxy = boxes.xyxy[i].tolist()
                        x1, y1, x2, y2 = [int(v) for v in xyxy]
                        conf = float(boxes.conf[i])

                        current_track_ids.add(track_id)

                        # Normalised centroid
                        cx_norm = ((x1 + x2) / 2) / w_frame
                        cy_norm = ((y1 + y2) / 2) / h_frame

                        # ---------------------------------------------------
                        # Visitor Re-ID & session assignment
                        # ---------------------------------------------------
                        visitor_id, is_new_entry, is_reentry = visitor_tracker.update_track(
                            track_id, frame, x1, y1, x2, y2, conf, now_mono
                        )
                        state = visitor_tracker.get_state(track_id)
                        is_staff = state.is_staff if state else False

                        # ---------------------------------------------------
                        # Entry / Exit detection (entry_exit cameras only)
                        # ---------------------------------------------------
                        if line_detector is not None:
                            crossing = line_detector.update(track_id, cy_norm)
                            if crossing == "ENTRY":
                                seq = visitor_tracker.increment_session_seq(track_id)
                                if is_reentry:
                                    evt = build_event(
                                        store_id=store_id,
                                        camera_id=camera_id,
                                        visitor_id=visitor_id,
                                        event_type="REENTRY",
                                        timestamp=timestamp,
                                        zone_id=None,
                                        dwell_ms=0,
                                        is_staff=is_staff,
                                        confidence=conf,
                                        session_seq=seq,
                                    )
                                    emitter.emit(evt)
                                    events_emitted += 1
                                evt = build_event(
                                    store_id=store_id,
                                    camera_id=camera_id,
                                    visitor_id=visitor_id,
                                    event_type="ENTRY",
                                    timestamp=timestamp,
                                    zone_id=None,
                                    dwell_ms=0,
                                    is_staff=is_staff,
                                    confidence=conf,
                                    session_seq=seq,
                                )
                                emitter.emit(evt)
                                events_emitted += 1

                            elif crossing == "EXIT":
                                seq = visitor_tracker.increment_session_seq(track_id)
                                # Flush any active zone dwell
                                for ev_type, zone_id, dwell_ms in dwell_tracker.flush_visitor(
                                    visitor_id, now_mono
                                ):
                                    zone_evt = build_event(
                                        store_id=store_id,
                                        camera_id=camera_id,
                                        visitor_id=visitor_id,
                                        event_type=ev_type,
                                        timestamp=timestamp,
                                        zone_id=zone_id,
                                        dwell_ms=dwell_ms,
                                        is_staff=is_staff,
                                        confidence=conf,
                                        session_seq=visitor_tracker.increment_session_seq(track_id),
                                    )
                                    emitter.emit(zone_evt)
                                    events_emitted += 1
                                evt = build_event(
                                    store_id=store_id,
                                    camera_id=camera_id,
                                    visitor_id=visitor_id,
                                    event_type="EXIT",
                                    timestamp=timestamp,
                                    zone_id=None,
                                    dwell_ms=0,
                                    is_staff=is_staff,
                                    confidence=conf,
                                    session_seq=seq,
                                )
                                emitter.emit(evt)
                                events_emitted += 1
                                visitor_tracker.mark_exited(track_id, now_mono)
                                if line_detector:
                                    line_detector.remove_track(track_id)

                        # ---------------------------------------------------
                        # Zone classification (floor + billing cameras)
                        # ---------------------------------------------------
                        zone_id = zone_classifier.classify(cx_norm, cy_norm)
                        queue_depth = queue_tracker.update(visitor_id, zone_id)

                        # Emit zone events (ZONE_ENTER, ZONE_EXIT, ZONE_DWELL)
                        for ev_type, z_id, dwell_ms in dwell_tracker.update(
                            visitor_id, zone_id, now_mono
                        ):
                            sku_zone = store_sku_zones.get(z_id)

                            # Cross-camera dedup for ZONE_ENTER
                            dedup_key = (visitor_id, z_id)
                            if ev_type == "ZONE_ENTER":
                                last_emit = zone_enter_dedup.get(dedup_key, 0)
                                if (now_mono - last_emit) < CROSS_CAM_DEDUP_WINDOW:
                                    continue
                                zone_enter_dedup[dedup_key] = now_mono

                            seq = visitor_tracker.increment_session_seq(track_id)

                            # BILLING_QUEUE_JOIN for billing zone entry while queue > 0
                            if ev_type == "ZONE_ENTER" and z_id in BILLING_ZONE_IDS and queue_depth > 1:
                                billing_evt = build_event(
                                    store_id=store_id,
                                    camera_id=camera_id,
                                    visitor_id=visitor_id,
                                    event_type="BILLING_QUEUE_JOIN",
                                    timestamp=timestamp,
                                    zone_id=z_id,
                                    dwell_ms=0,
                                    is_staff=is_staff,
                                    confidence=conf,
                                    queue_depth=queue_depth,
                                    sku_zone=sku_zone,
                                    session_seq=seq,
                                )
                                emitter.emit(billing_evt)
                                events_emitted += 1

                            zone_evt = build_event(
                                store_id=store_id,
                                camera_id=camera_id,
                                visitor_id=visitor_id,
                                event_type=ev_type,
                                timestamp=timestamp,
                                zone_id=z_id,
                                dwell_ms=dwell_ms,
                                is_staff=is_staff,
                                confidence=conf,
                                queue_depth=queue_depth if z_id in BILLING_ZONE_IDS else None,
                                sku_zone=sku_zone,
                                session_seq=seq,
                            )
                            emitter.emit(zone_evt)
                            events_emitted += 1

            # Detect tracks that disappeared (left frame without EXIT crossing)
            lost_tracks = prev_track_ids - current_track_ids
            for tid in lost_tracks:
                state = visitor_tracker.get_state(tid)
                if state:
                    for ev_type, z_id, dwell_ms in dwell_tracker.flush_visitor(
                        state.visitor_id, now_mono
                    ):
                        seq = visitor_tracker.increment_session_seq(tid)
                        zone_evt = build_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=state.visitor_id,
                            event_type=ev_type,
                            timestamp=timestamp,
                            zone_id=z_id,
                            dwell_ms=dwell_ms,
                            is_staff=state.is_staff,
                            confidence=0.5,  # uncertainty for lost tracks
                            session_seq=seq,
                        )
                        emitter.emit(zone_evt)
                        events_emitted += 1
                    visitor_tracker.mark_exited(tid, now_mono)

            prev_track_ids = current_track_ids

            if frame_index % (fps * 60) < frame_step:
                print(f"[detect] frame {frame_index}/{total_frames} "
                      f"({frame_index/total_frames*100:.1f}%) | "
                      f"events={events_emitted} | "
                      f"active_tracks={len(current_track_ids)}")

    finally:
        cap.release()
        emitter.close()

    print(f"[detect] Finished. Total events emitted: {events_emitted}")
    return events_emitted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CCTV detection pipeline")
    p.add_argument("--video", required=True, help="Path to video clip")
    p.add_argument("--store-id", required=True, help="Store ID (e.g. STORE_BLR_001)")
    p.add_argument("--camera-id", required=True, help="Camera ID (e.g. CAM_ENTRY_01)")
    p.add_argument("--layout", default="store_layout.json", help="Path to store_layout.json")
    p.add_argument("--output", default="events/output.jsonl", help="Output JSONL path")
    p.add_argument(
        "--clip-start",
        default="2026-04-10T10:00:00Z",
        help="Clip recording start as ISO-8601 UTC",
    )
    p.add_argument("--api-url", default=None, help="API base URL for real-time ingest")
    p.add_argument("--frame-step", type=int, default=3, help="Process every Nth frame")
    p.add_argument("--model", default="yolov8n.pt", help="YOLOv8 model variant")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    with open(args.layout, encoding="utf-8") as f:
        layout_data = json.load(f)

    store_layout = layout_data.get(args.store_id)
    if not store_layout:
        print(f"ERROR: store_id '{args.store_id}' not found in {args.layout}", file=sys.stderr)
        sys.exit(1)

    cameras = store_layout.get("cameras", {})
    cam_config = cameras.get(args.camera_id)
    if not cam_config:
        print(f"ERROR: camera_id '{args.camera_id}' not found for store '{args.store_id}'",
              file=sys.stderr)
        sys.exit(1)

    camera_type = cam_config.get("type", CAM_TYPE_FLOOR)
    roi_polygons = cam_config.get("roi_polygons", {})
    entry_line_pos = cam_config.get("entry_line", {}).get("normalized_position")

    process_clip(
        video_path=args.video,
        store_id=args.store_id,
        camera_id=args.camera_id,
        camera_type=camera_type,
        layout=store_layout,
        roi_polygons=roi_polygons,
        entry_line_pos=entry_line_pos,
        clip_start_iso=args.clip_start,
        output_path=args.output,
        api_url=args.api_url,
        frame_step=args.frame_step,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
