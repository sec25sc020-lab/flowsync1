"""Optional YOLO inference; a missing model never falls back to invented detections."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

CLASSES = {
    "car": "car",
    "bus": "bus",
    "truck": "truck",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "ambulance": "emergency",
    "fire truck": "emergency",
}


def detect_media(contents: bytes, filename: str, content_type: str) -> dict[str, Any]:
    model_path = os.getenv("YOLO_MODEL_PATH")
    if not model_path or not Path(model_path).is_file():
        raise RuntimeError("YOLO_MODEL_PATH is not configured with an existing model. Install the optional vision dependencies and configure a compatible weights file.")
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Computer-vision dependencies are missing. Install backend/requirements-vision.txt.") from exc

    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary.write(contents)
        temporary_path = temporary.name
    try:
        model = YOLO(model_path)
        if content_type.startswith("image/"):
            results = [model(temporary_path, verbose=False)[0]]
        else:
            capture = cv2.VideoCapture(temporary_path)
            if not capture.isOpened():
                raise ValueError("The uploaded video could not be opened.")
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            stride = max(1, total_frames // 8)
            results = []
            index = 0
            while len(results) < 8:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % stride == 0:
                    results.append(model(frame, verbose=False)[0])
                index += 1
            capture.release()
            if not results:
                raise ValueError("The uploaded video contains no readable frames.")

        counts = {name: 0 for name in ("car", "bus", "truck", "motorcycle", "emergency")}
        detections: list[dict[str, Any]] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                class_name = str(names[int(box.cls[0])]).lower()
                category = CLASSES.get(class_name)
                if category is None:
                    continue
                counts[category] += 1
                x1, y1, x2, y2 = [round(float(value)) for value in box.xyxy[0]]
                detections.append({
                    "class": category,
                    "confidence": round(float(box.conf[0]), 3),
                    "box": [x1, y1, x2, y2],
                })
        total = sum(counts.values())
        return {
            "source": "uploaded-media",
            "status": "analyzed",
            "counts": counts,
            "total_vehicles": total,
            "detections": detections,
            "sampled_frames": len(results),
            "media_width": int(results[0].orig_shape[1]),
            "media_height": int(results[0].orig_shape[0]),
            "congestion": "Critical" if total >= 40 else "High" if total >= 24 else "Medium" if total >= 10 else "Low",
        }
    finally:
        Path(temporary_path).unlink(missing_ok=True)
