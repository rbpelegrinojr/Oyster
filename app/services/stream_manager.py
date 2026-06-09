"""
Stream Manager

Manages one background thread per active camera.  Each thread:
  1. Reads frames from the camera's RTSP URL via OpenCV.
  2. Runs face detection every N frames (configurable for performance).
  3. Passes detected faces through liveness detection.
  4. Identifies live faces (known person / INTRUDER).
  5. Checks INTRUDER faces against the imaginary line (if configured).
  6. Logs intruder events and saves snapshots.
  7. Annotates the frame with bounding boxes and labels.
  8. Stores the latest annotated JPEG in a thread-safe buffer for streaming.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Dict, Optional

import cv2
import numpy as np

from .face_service import FaceService
from .liveness import LivenessDetector
from .line_crossing import LineCrossingDetector

# ---------------------------------------------------------------------------
# Colour palette (BGR)
# ---------------------------------------------------------------------------
_COLOUR_KNOWN = (57, 163, 22)       # green
_COLOUR_INTRUDER = (50, 50, 220)    # red (BGR)
_COLOUR_LINE = (0, 165, 255)        # orange
_COLOUR_LABEL_BG_KNOWN = (36, 157, 159)   # primary teal
_COLOUR_LABEL_BG_INTRUDER = (38, 38, 220)

_PROCESS_EVERY_N = 3   # run recognition every N frames for performance
_SNAPSHOT_COOLDOWN = 10  # seconds between snapshots for the same camera
_RECONNECT_DELAY = 5    # seconds before attempting RTSP reconnect


class CameraWorker:
    """Background RTSP reader + processor for a single camera."""

    def __init__(
        self,
        camera_id: int,
        rtsp_url: str,
        face_svc: FaceService,
        snapshots_dir: str,
        db_callback,  # callable(camera_id, event_type, snapshot_path)
        line_config_callback,  # callable(camera_id) -> LineConfig | None
    ) -> None:
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self._face_svc = face_svc
        self._snapshots_dir = snapshots_dir
        self._db_callback = db_callback
        self._line_config_callback = line_config_callback

        self._liveness = LivenessDetector()
        self._line_crossing = LineCrossingDetector()

        self._lock = threading.Lock()
        self._frame_jpeg: Optional[bytes] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot_time: float = 0.0

        # Simple centroid tracker: face_id counter
        self._next_face_id = 0
        self._tracked_faces: Dict[int, tuple] = {}  # face_id -> centroid

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"camera-{self.camera_id}"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def get_frame_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._frame_jpeg

    # ------------------------------------------------------------------
    def _set_frame(self, frame: np.ndarray) -> None:
        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            with self._lock:
                self._frame_jpeg = buf.tobytes()

    # ------------------------------------------------------------------
    def _assign_face_ids(
        self, centroids: list[tuple[float, float]]
    ) -> list[int]:
        """
        Nearest-neighbour centroid matching to assign persistent face IDs
        across consecutive frames.
        """
        if not self._tracked_faces:
            ids = []
            for c in centroids:
                fid = self._next_face_id
                self._next_face_id += 1
                self._tracked_faces[fid] = c
                ids.append(fid)
            return ids

        assigned: list[int] = []
        used_ids: set[int] = set()
        for c in centroids:
            best_id = -1
            best_dist = float("inf")
            for fid, prev_c in self._tracked_faces.items():
                if fid in used_ids:
                    continue
                dist = ((c[0] - prev_c[0]) ** 2 + (c[1] - prev_c[1]) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_id = fid
            if best_id == -1 or best_dist > 150:
                best_id = self._next_face_id
                self._next_face_id += 1
            used_ids.add(best_id)
            self._tracked_faces[best_id] = c
            assigned.append(best_id)

        # Remove stale tracks
        active = set(assigned)
        stale = [fid for fid in self._tracked_faces if fid not in active]
        for fid in stale:
            del self._tracked_faces[fid]
        self._liveness.purge_stale(active)
        self._line_crossing.purge_stale(active)
        return assigned

    # ------------------------------------------------------------------
    def _save_snapshot(self, frame: np.ndarray) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"cam{self.camera_id}_{ts}.jpg"
        path = os.path.join(self._snapshots_dir, filename)
        cv2.imwrite(path, frame)
        return f"snapshots/{filename}"

    # ------------------------------------------------------------------
    def _draw_annotations(
        self,
        frame: np.ndarray,
        face_locations: list,
        names: list[str],
        live_flags: list[bool],
        line_config,
    ) -> np.ndarray:
        h, w = frame.shape[:2]

        # Draw imaginary line
        if line_config and line_config.enabled:
            x1 = int(line_config.x1 * w)
            y1 = int(line_config.y1 * h)
            x2 = int(line_config.x2 * w)
            y2 = int(line_config.y2 * h)
            cv2.line(frame, (x1, y1), (x2, y2), _COLOUR_LINE, 2)

        for (top, right, bottom, left), name, is_live in zip(
            face_locations, names, live_flags
        ):
            if not is_live:
                # Grey out non-live faces
                colour = (128, 128, 128)
                label = "LIVENESS FAIL"
            elif name == "INTRUDER":
                colour = _COLOUR_INTRUDER
                label = "INTRUDER"
            else:
                colour = _COLOUR_KNOWN
                label = name

            cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)

            label_bg = _COLOUR_LABEL_BG_INTRUDER if name == "INTRUDER" else _COLOUR_LABEL_BG_KNOWN
            if not is_live:
                label_bg = (80, 80, 80)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (left, top - th - 10), (left + tw + 6, top), label_bg, -1)
            cv2.putText(
                frame,
                label,
                (left + 3, top - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Timestamp overlay
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        return frame

    # ------------------------------------------------------------------
    def _run(self) -> None:
        frame_count = 0
        last_names: list[str] = []
        last_locations: list = []
        last_live: list[bool] = []

        while not self._stop_event.is_set():
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                print(f"[Camera {self.camera_id}] Cannot open {self.rtsp_url}. Retrying …")
                # Show an offline placeholder
                placeholder = self._placeholder_frame()
                self._set_frame(placeholder)
                self._stop_event.wait(_RECONNECT_DELAY)
                continue

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[Camera {self.camera_id}] Stream connected.")

            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    print(f"[Camera {self.camera_id}] Frame read failed. Reconnecting …")
                    break

                frame_count += 1
                h, w = frame.shape[:2]

                if frame_count % _PROCESS_EVERY_N == 0:
                    small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                    locations_small = self._face_svc.detect_locations(rgb_small)

                    # Scale back to full resolution
                    locations = [
                        (t * 2, r * 2, b * 2, l * 2)
                        for (t, r, b, l) in locations_small
                    ]

                    centroids = [
                        ((l + r) / 2, (t + b) / 2) for (t, r, b, l) in locations
                    ]
                    face_ids = self._assign_face_ids(centroids)

                    if locations:
                        rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        names = self._face_svc.identify(rgb_full, locations)
                    else:
                        names = []

                    live_flags: list[bool] = []
                    for idx, (loc, fid) in enumerate(zip(locations, face_ids)):
                        live = self._liveness.check(frame, loc, fid)
                        live_flags.append(live)

                    # Intruder + line-crossing logic
                    line_cfg = self._line_config_callback(self.camera_id)
                    now = time.time()
                    for idx, (name, is_live, fid, centroid) in enumerate(
                        zip(names, live_flags, face_ids, centroids)
                    ):
                        if name == "INTRUDER" and is_live:
                            # Log face-detection intruder (with cooldown)
                            if now - self._last_snapshot_time >= _SNAPSHOT_COOLDOWN:
                                snapshot = self._save_snapshot(frame.copy())
                                self._last_snapshot_time = now
                                self._db_callback(self.camera_id, "face_detection", snapshot)

                            # Check line crossing
                            if line_cfg and line_cfg.enabled:
                                crossed = self._line_crossing.check(
                                    fid,
                                    centroid,
                                    (line_cfg.x1, line_cfg.y1, line_cfg.x2, line_cfg.y2),
                                    w,
                                    h,
                                )
                                if crossed:
                                    snap2 = self._save_snapshot(frame.copy())
                                    self._db_callback(
                                        self.camera_id, "line_crossing", snap2
                                    )

                    last_names = names
                    last_locations = locations
                    last_live = live_flags

                annotated = self._draw_annotations(
                    frame.copy(),
                    last_locations,
                    last_names,
                    last_live,
                    self._line_config_callback(self.camera_id),
                )
                self._set_frame(annotated)

            cap.release()
            if not self._stop_event.is_set():
                self._stop_event.wait(_RECONNECT_DELAY)

    # ------------------------------------------------------------------
    @staticmethod
    def _placeholder_frame() -> np.ndarray:
        img = np.zeros((360, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)
        cv2.putText(
            img, "Camera Offline", (180, 190),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2,
        )
        return img


# ---------------------------------------------------------------------------
# StreamManager – owns all CameraWorkers
# ---------------------------------------------------------------------------

class StreamManager:
    def __init__(self, app) -> None:
        self._app = app
        self._workers: Dict[int, CameraWorker] = {}
        self._lock = threading.Lock()

        # Lazy-initialise FaceService once (shared across all cameras)
        with app.app_context():
            self._face_svc = FaceService(app.config["MODELS_DIR"])

    # ------------------------------------------------------------------
    def _db_callback(self, camera_id: int, event_type: str, snapshot_path: str) -> None:
        from app.models import IntruderLog
        from app.database import db

        with self._app.app_context():
            log = IntruderLog(
                camera_id=camera_id,
                event_type=event_type,
                snapshot_path=snapshot_path,
            )
            db.session.add(log)
            db.session.commit()

    def _line_config_callback(self, camera_id: int):
        from app.models import LineConfig

        with self._app.app_context():
            return LineConfig.query.filter_by(camera_id=camera_id).first()

    # ------------------------------------------------------------------
    def start_all(self) -> None:
        from app.models import Camera

        with self._app.app_context():
            cameras = Camera.query.filter_by(is_active=True).all()
            for cam in cameras:
                self._start_worker(cam.id, cam.rtsp_url)

    def _start_worker(self, camera_id: int, rtsp_url: str) -> None:
        with self._lock:
            if camera_id in self._workers:
                self._workers[camera_id].stop()
            worker = CameraWorker(
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                face_svc=self._face_svc,
                snapshots_dir=self._app.config["SNAPSHOTS_DIR"],
                db_callback=self._db_callback,
                line_config_callback=self._line_config_callback,
            )
            worker.start()
            self._workers[camera_id] = worker

    def stop_worker(self, camera_id: int) -> None:
        with self._lock:
            if camera_id in self._workers:
                self._workers[camera_id].stop()
                del self._workers[camera_id]

    def restart_worker(self, camera_id: int, rtsp_url: str) -> None:
        self._start_worker(camera_id, rtsp_url)

    def get_frame(self, camera_id: int) -> Optional[bytes]:
        with self._lock:
            worker = self._workers.get(camera_id)
        return worker.get_frame_jpeg() if worker else None

    def reload_encodings(self) -> None:
        self._face_svc.load_encodings()

    def face_service(self) -> FaceService:
        return self._face_svc

    def get_training_frame(self, camera_id: int) -> Optional[bytes]:
        """Return a raw (unannotated) JPEG frame for training capture."""
        return self.get_frame(camera_id)
