"""
Line-crossing detection helper.

Each camera may have one imaginary line defined by two endpoints
(stored as fractions of frame width/height so they scale with resolution).

Algorithm
---------
For every unknown face detected in a frame we track the face's centroid
between consecutive frames.  If the sign of the cross-product
  (P2 - P1) × (centroid - P1)
flips between frames the face has crossed the line.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np


def _side(p1: np.ndarray, p2: np.ndarray, point: np.ndarray) -> float:
    """Signed cross-product (Z component) – positive or negative."""
    return float((p2[0] - p1[0]) * (point[1] - p1[1]) - (p2[1] - p1[1]) * (point[0] - p1[0]))


class LineCrossingDetector:
    """Per-camera stateful line-crossing detector."""

    def __init__(self) -> None:
        # face_id -> (side_sign, centroid)
        self._prev_sides: Dict[int, float] = {}

    def reset(self) -> None:
        self._prev_sides.clear()

    def check(
        self,
        face_id: int,
        centroid: Tuple[float, float],
        line: Tuple[float, float, float, float],
        frame_w: int,
        frame_h: int,
    ) -> bool:
        """
        Return True if face *face_id* just crossed the line.

        centroid : (x, y) in pixel coordinates
        line     : (x1_frac, y1_frac, x2_frac, y2_frac) fractional coords
        """
        x1 = line[0] * frame_w
        y1 = line[1] * frame_h
        x2 = line[2] * frame_w
        y2 = line[3] * frame_h

        p1 = np.array([x1, y1])
        p2 = np.array([x2, y2])
        pt = np.array([centroid[0], centroid[1]])

        current_side = _side(p1, p2, pt)

        crossed = False
        if face_id in self._prev_sides:
            prev_side = self._prev_sides[face_id]
            # Sign flip means crossed
            if prev_side != 0 and current_side != 0:
                if (prev_side > 0) != (current_side > 0):
                    crossed = True

        self._prev_sides[face_id] = current_side
        return crossed

    def purge_stale(self, active_ids: set[int]) -> None:
        stale = [fid for fid in self._prev_sides if fid not in active_ids]
        for fid in stale:
            del self._prev_sides[fid]
