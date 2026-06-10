"""
Polygon zone intrusion detection.

Replaces the line-crossing system with a configurable polygon zone.
An intrusion event is triggered only when an unknown face (INTRUDER)
that passes liveness detection is located inside the defined zone.

Algorithm
---------
Uses the ray-casting (point-in-polygon) algorithm to determine whether
a face centroid is inside the configured polygon zone.  This is a standard
computational geometry algorithm that counts how many times a ray from the
point crosses the polygon boundary – an odd count means the point is inside.
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


class ZoneDetector:
    """Stateless polygon zone containment checker."""

    @staticmethod
    def is_inside(
        point: Tuple[float, float],
        polygon: List[Tuple[int, int]],
    ) -> bool:
        """
        Return True if *point* is inside the *polygon*.

        point   : (x, y) in pixel coordinates (face centroid)
        polygon : list of (x, y) pixel coordinate tuples defining the zone
        """
        if len(polygon) < 3:
            return False

        # OpenCV pointPolygonTest returns positive if inside, 0 on edge, negative outside
        contour = np.array(polygon, dtype=np.float32).reshape((-1, 1, 2))
        result = cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False)
        return result >= 0  # inside or on the boundary
