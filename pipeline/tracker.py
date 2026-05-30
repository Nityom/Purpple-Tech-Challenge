"""
tracker.py — Re-ID and visitor session management.

Wraps ByteTrack (via ultralytics) track IDs with a Re-ID layer that:
  - Assigns stable visitor_id tokens per session (VIS_xxxxxxxx)
  - Detects re-entry by matching appearance fingerprints (HSV colour histogram)
  - Classifies staff via uniform colour and zone persistence heuristics
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REID_SIMILARITY_THRESHOLD = 0.85   # cosine similarity for re-entry match
REID_CACHE_TTL_SECONDS = 1800      # 30 minutes
STAFF_UNIFORM_HUE_MIN = 90         # HSV hue — teal/green (configurable)
STAFF_UNIFORM_HUE_MAX = 130
STAFF_UNIFORM_SAT_MIN = 60         # must be somewhat saturated (not grey)
STAFF_MIN_PRESENCE_SECONDS = 3600  # 60 minutes in view = staff
HISTOGRAM_BINS_HUE = 32
HISTOGRAM_BINS_SAT = 16

# Fraction of bbox height used for torso region (avoids head/legs)
TORSO_TOP = 0.25
TORSO_BOTTOM = 0.65


# ---------------------------------------------------------------------------
# Appearance fingerprint
# ---------------------------------------------------------------------------

def extract_appearance_fingerprint(
    frame: np.ndarray, x1: int, y1: int, x2: int, y2: int
) -> Optional[np.ndarray]:
    """
    Extract a normalised HSV colour histogram from the torso region of a
    bounding box.  Returns a 1D float32 array of length
    HISTOGRAM_BINS_HUE * HISTOGRAM_BINS_SAT, or None if the crop is too small.
    """
    h = y2 - y1
    w = x2 - x1
    if h < 20 or w < 10:
        return None

    # Crop torso region
    ty1 = int(y1 + h * TORSO_TOP)
    ty2 = int(y1 + h * TORSO_BOTTOM)
    crop = frame[ty1:ty2, x1:x2]
    if crop.size == 0:
        return None

    # Resize for consistent histogram
    crop = cv2.resize(crop, (64, 64))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    hist = cv2.calcHist(
        [hsv], [0, 1],
        None,
        [HISTOGRAM_BINS_HUE, HISTOGRAM_BINS_SAT],
        [0, 180, 0, 256],
    )
    hist = hist.flatten().astype(np.float32)
    norm = np.linalg.norm(hist)
    if norm == 0:
        return None
    return hist / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two already-normalised histograms."""
    return float(np.dot(a, b))


def is_staff_uniform(fingerprint: np.ndarray) -> bool:
    """
    Heuristic: check if the dominant hue in the histogram falls within the
    staff uniform hue range.
    """
    # Re-shape histogram back to 2D (hue × saturation)
    hist_2d = fingerprint.reshape(HISTOGRAM_BINS_HUE, HISTOGRAM_BINS_SAT)
    # Sum over saturation axis to get hue distribution
    hue_dist = hist_2d.sum(axis=1)
    peak_hue_bin = int(np.argmax(hue_dist))
    # Map bin index to HSV hue value (0–180)
    peak_hue = peak_hue_bin * (180 / HISTOGRAM_BINS_HUE)
    return STAFF_UNIFORM_HUE_MIN <= peak_hue <= STAFF_UNIFORM_HUE_MAX


def make_visitor_id(seed: str) -> str:
    """Generate a stable VIS_xxxxxxxx token from a seed string."""
    digest = hashlib.sha1(seed.encode()).hexdigest()[:8]
    return f"VIS_{digest}"


# ---------------------------------------------------------------------------
# Track state
# ---------------------------------------------------------------------------

@dataclass
class TrackState:
    track_id: int
    visitor_id: str
    first_seen_at: float
    last_seen_at: float
    fingerprint: Optional[np.ndarray]
    is_staff: bool = False
    has_exited: bool = False
    session_seq: int = 0

    def age_seconds(self, now: float) -> float:
        return now - self.first_seen_at


@dataclass
class ReIDCacheEntry:
    visitor_id: str
    fingerprint: np.ndarray
    cached_at: float


# ---------------------------------------------------------------------------
# VisitorTracker
# ---------------------------------------------------------------------------

class VisitorTracker:
    """
    Maintains visitor_id assignments for ByteTrack track_ids.
    Handles Re-ID (re-entry) and staff detection.
    """

    def __init__(self, reid_cache_ttl: float = REID_CACHE_TTL_SECONDS):
        self._reid_cache_ttl = reid_cache_ttl
        self._active: dict[int, TrackState] = {}       # track_id → TrackState
        self._reid_cache: list[ReIDCacheEntry] = []    # exited visitors

    def _find_reid_match(
        self, fingerprint: Optional[np.ndarray], now: float
    ) -> Optional[str]:
        """Look for a matching fingerprint in the Re-ID cache."""
        if fingerprint is None:
            return None
        # Expire stale cache entries
        self._reid_cache = [
            e for e in self._reid_cache
            if (now - e.cached_at) < self._reid_cache_ttl
        ]
        best_sim = 0.0
        best_visitor_id = None
        for entry in self._reid_cache:
            sim = cosine_similarity(fingerprint, entry.fingerprint)
            if sim > best_sim:
                best_sim = sim
                best_visitor_id = entry.visitor_id
        if best_sim >= REID_SIMILARITY_THRESHOLD:
            return best_visitor_id
        return None

    def update_track(
        self,
        track_id: int,
        frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        confidence: float,
        now: float,
    ) -> tuple[str, bool, bool]:
        """
        Update or create a track.
        Returns (visitor_id, is_new_entry, is_reentry).
        """
        fingerprint = extract_appearance_fingerprint(frame, x1, y1, x2, y2)

        if track_id in self._active:
            state = self._active[track_id]
            state.last_seen_at = now
            # Update fingerprint with rolling average for robustness
            if fingerprint is not None and state.fingerprint is not None:
                state.fingerprint = (state.fingerprint * 0.7 + fingerprint * 0.3)
                norm = np.linalg.norm(state.fingerprint)
                if norm > 0:
                    state.fingerprint /= norm
            # Check staff by long presence
            if state.age_seconds(now) >= STAFF_MIN_PRESENCE_SECONDS:
                state.is_staff = True
            elif fingerprint is not None and is_staff_uniform(fingerprint):
                state.is_staff = True
            return state.visitor_id, False, False

        # New track — check Re-ID cache
        matched_id = self._find_reid_match(fingerprint, now)
        is_reentry = matched_id is not None

        if matched_id:
            visitor_id = matched_id
            # Remove from cache so it doesn't match again until next exit
            self._reid_cache = [e for e in self._reid_cache if e.visitor_id != matched_id]
        else:
            # Brand new visitor
            seed = f"{track_id}_{now}_{id(self)}"
            visitor_id = make_visitor_id(seed)

        is_staff_flag = (fingerprint is not None and is_staff_uniform(fingerprint))

        self._active[track_id] = TrackState(
            track_id=track_id,
            visitor_id=visitor_id,
            first_seen_at=now,
            last_seen_at=now,
            fingerprint=fingerprint,
            is_staff=is_staff_flag,
            has_exited=False,
        )
        return visitor_id, True, is_reentry

    def get_state(self, track_id: int) -> Optional[TrackState]:
        return self._active.get(track_id)

    def mark_exited(self, track_id: int, now: float) -> Optional[TrackState]:
        """Mark a track as exited and move to Re-ID cache."""
        state = self._active.pop(track_id, None)
        if state and state.fingerprint is not None:
            state.has_exited = True
            self._reid_cache.append(
                ReIDCacheEntry(
                    visitor_id=state.visitor_id,
                    fingerprint=state.fingerprint.copy(),
                    cached_at=now,
                )
            )
        return state

    def increment_session_seq(self, track_id: int) -> int:
        state = self._active.get(track_id)
        if state:
            state.session_seq += 1
            return state.session_seq
        return 0

    def get_all_active_track_ids(self) -> list[int]:
        return list(self._active.keys())
