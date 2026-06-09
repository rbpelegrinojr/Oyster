"""
Face recognition service.

Loads face encodings from models_store/encodings.pkl and provides
identify() to classify a detected face as a known person or INTRUDER.
"""

from __future__ import annotations

import os
import pickle
import threading
from typing import List, Tuple

import numpy as np

try:
    import face_recognition  # type: ignore

    _FR_AVAILABLE = True
except ImportError:
    _FR_AVAILABLE = False
    print("[FaceService] face_recognition not installed – recognition disabled.")

ENCODINGS_FILE = "encodings.pkl"
TOLERANCE = 0.5  # lower = stricter match


class FaceService:
    """Thread-safe face encoding store and identifier."""

    def __init__(self, models_dir: str) -> None:
        self._models_dir = models_dir
        self._lock = threading.Lock()
        self._known_encodings: List[np.ndarray] = []
        self._known_names: List[str] = []
        self.load_encodings()

    # ------------------------------------------------------------------
    def _encodings_path(self) -> str:
        return os.path.join(self._models_dir, ENCODINGS_FILE)

    def load_encodings(self) -> None:
        path = self._encodings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            with self._lock:
                self._known_encodings = data.get("encodings", [])
                self._known_names = data.get("names", [])
            print(
                f"[FaceService] Loaded {len(self._known_names)} known face(s)."
            )
        except Exception as exc:
            print(f"[FaceService] Failed to load encodings: {exc}")

    # ------------------------------------------------------------------
    def identify(
        self,
        frame_rgb: np.ndarray,
        face_locations: List[Tuple[int, int, int, int]],
    ) -> List[str]:
        """
        Return a list of names corresponding to *face_locations*.
        'INTRUDER' is returned for unrecognised faces.
        """
        if not _FR_AVAILABLE or not face_locations:
            return ["INTRUDER"] * len(face_locations)

        encodings = face_recognition.face_encodings(frame_rgb, face_locations)
        results: List[str] = []

        with self._lock:
            known_enc = list(self._known_encodings)
            known_names = list(self._known_names)

        for enc in encodings:
            if not known_enc:
                results.append("INTRUDER")
                continue
            matches = face_recognition.compare_faces(known_enc, enc, tolerance=TOLERANCE)
            face_distances = face_recognition.face_distance(known_enc, enc)
            if True in matches:
                best_idx = int(np.argmin(face_distances))
                results.append(known_names[best_idx])
            else:
                results.append("INTRUDER")
        return results

    # ------------------------------------------------------------------
    def detect_locations(
        self, frame_rgb: np.ndarray, model: str = "hog"
    ) -> List[Tuple[int, int, int, int]]:
        """Return face locations (top, right, bottom, left) in the frame."""
        if not _FR_AVAILABLE:
            return []
        return face_recognition.face_locations(frame_rgb, model=model)

    # ------------------------------------------------------------------
    def train(self, dataset_dir: str) -> Tuple[bool, str]:
        """
        Scan dataset_dir/<person_name>/ folders, compute encodings, save pkl.
        Returns (success, message).
        """
        if not _FR_AVAILABLE:
            return False, "face_recognition library not installed."

        encodings: List[np.ndarray] = []
        names: List[str] = []
        errors: List[str] = []

        person_dirs = [
            d
            for d in os.listdir(dataset_dir)
            if os.path.isdir(os.path.join(dataset_dir, d))
        ]
        if not person_dirs:
            return False, "No person folders found in dataset directory."

        import cv2  # local import to keep module lightweight

        for person_name in person_dirs:
            person_dir = os.path.join(dataset_dir, person_name)
            image_files = [
                f
                for f in os.listdir(person_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            for img_file in image_files:
                img_path = os.path.join(person_dir, img_file)
                img = cv2.imread(img_path)
                if img is None:
                    errors.append(f"Cannot read {img_path}")
                    continue
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb)
                encs = face_recognition.face_encodings(rgb, locs)
                for enc in encs:
                    encodings.append(enc)
                    names.append(person_name)

        if not encodings:
            return False, "No face encodings could be computed from the dataset."

        data = {"encodings": encodings, "names": names}
        path = self._encodings_path()
        with open(path, "wb") as f:
            pickle.dump(data, f)

        # Reload in-memory store
        self.load_encodings()

        msg = (
            f"Trained {len(set(names))} person(s), "
            f"{len(encodings)} encoding(s) total."
        )
        if errors:
            msg += f" ({len(errors)} image(s) skipped)"
        return True, msg
