"""
Liveness detection service.

Strategy (passive – no user cooperation required, suitable for CCTV):

1. **Motion variance** – A printed photo held still in front of the camera
   produces near-zero frame-to-frame difference inside the face ROI.
   A real person always shows micro-movements (breathing, blinking, tiny head
   sway) that generate measurable variance.

2. **Eye Aspect Ratio (EAR) blink detection** – Using dlib 68-point landmarks
   to detect at least one blink within a rolling window of frames. A flat
   printed image never blinks.

Both checks are combined: motion variance is fast and runs every frame;
EAR blink detection accumulates evidence over a short window.
"""

from __future__ import annotations

import os
import urllib.request
import bz2
from collections import deque
from typing import Deque, Tuple

import cv2
import numpy as np

try:
    import dlib  # type: ignore

    _DLIB_AVAILABLE = True
except ImportError:
    _DLIB_AVAILABLE = False

# ---------------------------------------------------------------------------
# dlib shape predictor – downloaded automatically on first use
# ---------------------------------------------------------------------------
_PREDICTOR_URL = (
    "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
)
_PREDICTOR_FILENAME = "shape_predictor_68_face_landmarks.dat"


def _get_predictor_path() -> str:
    base = os.environ.get("OYSTER_BASE_DIR", os.getcwd())
    return os.path.join(base, "models_store", _PREDICTOR_FILENAME)


def _ensure_predictor() -> str | None:
    path = _get_predictor_path()
    if os.path.exists(path):
        return path
    bz2_path = path + ".bz2"
    try:
        print("[Liveness] Downloading dlib shape predictor …")
        urllib.request.urlretrieve(_PREDICTOR_URL, bz2_path)
        with bz2.open(bz2_path, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        os.remove(bz2_path)
        print("[Liveness] Shape predictor downloaded.")
        return path
    except Exception as exc:
        print(f"[Liveness] Could not download shape predictor: {exc}")
        return None


# ---------------------------------------------------------------------------
# Eye Aspect Ratio helpers
# ---------------------------------------------------------------------------
_LEFT_EYE_IDX = list(range(36, 42))
_RIGHT_EYE_IDX = list(range(42, 48))
_EAR_THRESHOLD = 0.25  # below this → eye considered closed
_EAR_CONSEC_FRAMES = 2  # closed for at least this many consecutive frames
_BLINK_WINDOW = 30  # frames within which we require ≥1 blink


def _eye_aspect_ratio(eye_pts: np.ndarray) -> float:
    a = np.linalg.norm(eye_pts[1] - eye_pts[5])
    b = np.linalg.norm(eye_pts[2] - eye_pts[4])
    c = np.linalg.norm(eye_pts[0] - eye_pts[3])
    return (a + b) / (2.0 * c + 1e-6)


# ---------------------------------------------------------------------------
# Motion variance helpers
# ---------------------------------------------------------------------------
_MOTION_WINDOW = 10   # frames to accumulate
_MOTION_THRESHOLD = 2.0  # mean pixel std-dev below this → likely a photo
_MIN_FRAMES_BEFORE_PASS = 5  # require at least this many frames before passing


# ---------------------------------------------------------------------------
# Per-face state tracker (keyed by a simple face ID)
# ---------------------------------------------------------------------------
class _FaceState:
    def __init__(self) -> None:
        self.face_patches: Deque[np.ndarray] = deque(maxlen=_MOTION_WINDOW)
        self.ear_history: Deque[float] = deque(maxlen=_BLINK_WINDOW)
        self.blink_count: int = 0
        self.ear_consec_below: int = 0
        self.liveness_confirmed: bool = False


class LivenessDetector:
    """Stateful per-camera liveness checker."""

    def __init__(self) -> None:
        self._predictor = None
        self._detector = None
        self._face_states: dict[int, _FaceState] = {}
        self._init_dlib()

    def _init_dlib(self) -> None:
        if not _DLIB_AVAILABLE:
            print("[Liveness] dlib not available – EAR blink check disabled.")
            return
        predictor_path = _ensure_predictor()
        if predictor_path:
            self._detector = dlib.get_frontal_face_detector()
            self._predictor = dlib.shape_predictor(predictor_path)
        else:
            print("[Liveness] EAR blink check disabled (missing predictor).")

    # ------------------------------------------------------------------
    def _get_face_state(self, face_id: int) -> _FaceState:
        if face_id not in self._face_states:
            self._face_states[face_id] = _FaceState()
        return self._face_states[face_id]

    def purge_stale(self, active_ids: set[int]) -> None:
        """Remove state for faces no longer tracked."""
        stale = [fid for fid in self._face_states if fid not in active_ids]
        for fid in stale:
            del self._face_states[fid]

    # ------------------------------------------------------------------
    def check(
        self,
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int],
        face_id: int,
    ) -> bool:
        """
        Return True if the face at *face_location* passes liveness.

        face_location: (top, right, bottom, left) – face_recognition convention.
        face_id: caller-assigned integer to track state between frames.
        """
        top, right, bottom, left = face_location
        state = self._get_face_state(face_id)

        # ── 1. Motion variance check ──────────────────────────────────
        roi = frame[max(0, top): bottom, max(0, left): right]
        if roi.size == 0:
            return False
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        roi_resized = cv2.resize(roi_gray, (64, 64))
        state.face_patches.append(roi_resized.astype(np.float32))

        motion_passed = False
        if len(state.face_patches) >= _MIN_FRAMES_BEFORE_PASS:
            stack = np.stack(state.face_patches, axis=0)   # (N, 64, 64)
            motion_score = float(np.mean(np.std(stack, axis=0)))
            if motion_score >= _MOTION_THRESHOLD:
                motion_passed = True
            elif len(state.face_patches) >= _MOTION_WINDOW:
                # Accumulated full window but motion is too low – static image
                return False

        # ── 2. EAR blink check (if dlib available) ───────────────────
        if self._predictor is not None and self._detector is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rect = dlib.rectangle(left, top, right, bottom)
            shape = self._predictor(gray, rect)
            pts = np.array(
                [(shape.part(i).x, shape.part(i).y) for i in range(68)],
                dtype=np.float32,
            )
            left_eye = pts[_LEFT_EYE_IDX]
            right_eye = pts[_RIGHT_EYE_IDX]
            ear = (_eye_aspect_ratio(left_eye) + _eye_aspect_ratio(right_eye)) / 2.0
            state.ear_history.append(ear)

            if ear < _EAR_THRESHOLD:
                state.ear_consec_below += 1
            else:
                if state.ear_consec_below >= _EAR_CONSEC_FRAMES:
                    state.blink_count += 1
                state.ear_consec_below = 0

            # Once a blink is detected liveness is confirmed for this face
            if state.blink_count >= 1:
                state.liveness_confirmed = True

            if not state.liveness_confirmed and len(state.ear_history) >= _BLINK_WINDOW:
                # Haven't blinked in the window – likely a photo
                return False

        # Require positive motion evidence before passing liveness.
        # Do NOT give benefit of doubt while frames are still accumulating.
        if not motion_passed:
            return False

        return True
