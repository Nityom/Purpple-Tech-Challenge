"""
zones.py — Zone classification and dwell tracking.

Maps normalised bounding-box centroids to named store zones using polygon
ROI definitions from store_layout.json.  Maintains per-visitor dwell timers
and emits ZONE_DWELL events every 30 seconds of continuous presence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Polygon point-in-polygon test (ray casting)
# ---------------------------------------------------------------------------

def point_in_polygon(px: float, py: float, polygon: list[list[float]]) -> bool:
    """Return True if (px, py) is inside the polygon (normalised coordinates)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# ZoneClassifier — maps frame detections to zone names
# ---------------------------------------------------------------------------

class ZoneClassifier:
    """
    Given a camera's ROI polygon definitions (from store_layout.json),
    determine which zone a bounding box centroid falls in.
    """

    def __init__(self, roi_polygons: dict[str, list[list[float]]]):
        """
        roi_polygons: {"ZONE_NAME": [[x0,y0],[x1,y1],...], ...}
        Coordinates are normalised [0, 1] relative to frame width/height.
        """
        self.roi_polygons = roi_polygons

    def classify(self, cx_norm: float, cy_norm: float) -> Optional[str]:
        """
        Return the zone name for a centroid (cx_norm, cy_norm) in [0,1] space.
        Returns None if the centroid is in no defined zone.
        """
        for zone_name, polygon in self.roi_polygons.items():
            if point_in_polygon(cx_norm, cy_norm, polygon):
                return zone_name
        return None


# ---------------------------------------------------------------------------
# Entry/Exit line crossing detector
# ---------------------------------------------------------------------------

@dataclass
class LineCrossingDetector:
    """
    Virtual line crossing for ENTRY/EXIT detection.
    A person crossing the line from above (y increasing) → ENTRY
    A person crossing the line from below (y decreasing) → EXIT

    axis: "y" means a horizontal line at y = position (normalised)
    """
    position: float          # normalised y position of counting line
    axis: str = "y"          # "y" for horizontal line
    # Hysteresis: require crossing by at least this much to register
    hysteresis: float = 0.02

    _prev_side: dict[int, Optional[str]] = field(default_factory=dict)

    def update(self, track_id: int, cy_norm: float) -> Optional[str]:
        """
        Update position for track_id and return:
          "ENTRY" if the track crossed the line inbound
          "EXIT"  if the track crossed the line outbound
          None    if no crossing occurred
        """
        if self.axis == "y":
            side = "above" if cy_norm < self.position else "below"
        else:
            side = "left" if cy_norm < self.position else "right"

        prev = self._prev_side.get(track_id)
        self._prev_side[track_id] = side

        if prev is None or prev == side:
            return None

        # Crossing detected
        if prev == "above" and side == "below":
            return "ENTRY"
        if prev == "below" and side == "above":
            return "EXIT"
        return None

    def remove_track(self, track_id: int) -> None:
        self._prev_side.pop(track_id, None)


# ---------------------------------------------------------------------------
# DwellTracker — per visitor zone dwell accumulation
# ---------------------------------------------------------------------------

DWELL_EMIT_INTERVAL_SECONDS = 30.0


@dataclass
class ZonePresence:
    zone_id: str
    entered_at: float           # monotonic time
    last_dwell_emit_at: float   # monotonic time of last ZONE_DWELL emit
    dwell_accumulated_ms: int = 0


class DwellTracker:
    """
    Tracks how long each visitor spends in each zone.
    Returns a list of (event_type, zone_id, dwell_ms) tuples on each update.
    """

    def __init__(self) -> None:
        # visitor_id → ZonePresence (current zone only)
        self._presence: dict[str, ZonePresence] = {}

    def update(
        self, visitor_id: str, zone_id: Optional[str], now: float
    ) -> list[tuple[str, str, int]]:
        """
        Call on every detection update with the current zone (or None).
        Returns list of (event_type, zone_id, dwell_ms) to emit.
        """
        events_to_emit: list[tuple[str, str, int]] = []
        presence = self._presence.get(visitor_id)

        if zone_id is None:
            # Visitor left all zones or is in no zone
            if presence:
                dwell_ms = int((now - presence.entered_at) * 1000)
                events_to_emit.append(("ZONE_EXIT", presence.zone_id, dwell_ms))
                del self._presence[visitor_id]
            return events_to_emit

        if presence is None:
            # New zone entry
            self._presence[visitor_id] = ZonePresence(
                zone_id=zone_id,
                entered_at=now,
                last_dwell_emit_at=now,
            )
            events_to_emit.append(("ZONE_ENTER", zone_id, 0))
            return events_to_emit

        if presence.zone_id != zone_id:
            # Zone changed — exit old, enter new
            exit_dwell_ms = int((now - presence.entered_at) * 1000)
            events_to_emit.append(("ZONE_EXIT", presence.zone_id, exit_dwell_ms))
            self._presence[visitor_id] = ZonePresence(
                zone_id=zone_id,
                entered_at=now,
                last_dwell_emit_at=now,
            )
            events_to_emit.append(("ZONE_ENTER", zone_id, 0))
            return events_to_emit

        # Same zone — check for ZONE_DWELL emit
        elapsed_since_dwell = now - presence.last_dwell_emit_at
        if elapsed_since_dwell >= DWELL_EMIT_INTERVAL_SECONDS:
            dwell_ms = int(elapsed_since_dwell * 1000)
            presence.dwell_accumulated_ms += dwell_ms
            presence.last_dwell_emit_at = now
            events_to_emit.append(("ZONE_DWELL", zone_id, dwell_ms))

        return events_to_emit

    def flush_visitor(self, visitor_id: str, now: float) -> list[tuple[str, str, int]]:
        """Called when a visitor EXITs — emit final ZONE_EXIT if still in zone."""
        events: list[tuple[str, str, int]] = []
        presence = self._presence.pop(visitor_id, None)
        if presence:
            dwell_ms = int((now - presence.entered_at) * 1000)
            events.append(("ZONE_EXIT", presence.zone_id, dwell_ms))
        return events


# ---------------------------------------------------------------------------
# QueueDepthTracker — billing zone people counter
# ---------------------------------------------------------------------------

class QueueDepthTracker:
    """
    Counts persons in the billing/queue zone for BILLING_QUEUE_JOIN events.
    """

    def __init__(self, billing_zone_ids: set[str]):
        self.billing_zone_ids = billing_zone_ids
        self._in_zone: set[str] = set()

    def update(self, visitor_id: str, zone_id: Optional[str]) -> int:
        """Update and return current queue depth (customer count in billing zone)."""
        if zone_id in self.billing_zone_ids:
            self._in_zone.add(visitor_id)
        else:
            self._in_zone.discard(visitor_id)
        return len(self._in_zone)

    @property
    def depth(self) -> int:
        return len(self._in_zone)
