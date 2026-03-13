# src/detector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


BBox = Tuple[int, int, int, int]  # (x1, y1, x2, y2) pixel coords


@dataclass(frozen=True)
class VehicleDet:
    bbox: BBox
    conf: float
    cls: int


def _clamp_bbox_xyxy(b: BBox, w: int, h: int) -> Optional[BBox]:
    x1, y1, x2, y2 = b
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(0, min(x2, w - 1))
    y2 = max(0, min(y2, h - 1))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


class VehicleDetector:
    def __init__(
        self,
        model_path: str,
        conf: float = 0.35,
        iou: float = 0.5,
        classes: Optional[Sequence[int]] = None,
        imgsz: Union[int, Tuple[int, int]] = 416,
        device: Optional[Union[int, str]] = None,
        half: bool = False,
        max_det: int = 300,
        agnostic_nms: bool = False,
        verbose: bool = False,
    ) -> None:
        if YOLO is None:
            raise ImportError(
            )

        self.model = YOLO(model_path)
        self.conf = float(conf)
        self.iou = float(iou)
        self.classes = list(classes) if classes is not None else None
        self.imgsz = imgsz
        self.device = device
        self.half = bool(half)
        self.max_det = int(max_det)
        self.agnostic_nms = bool(agnostic_nms)
        self.verbose = bool(verbose)

    def detect(self, frame_bgr: np.ndarray) -> List[VehicleDet]:
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray):
            raise TypeError("frame_bgr must be a numpy ndarray.")
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            raise ValueError("frame_bgr must have shape (H, W, 3).")

        h, w = frame_bgr.shape[:2]

        # Ultralytics returns a list of Results (one per image)
        results = self.model.predict(
            source=frame_bgr,
            conf=self.conf,
            iou=self.iou,
            classes=self.classes,
            imgsz=self.imgsz,
            device=self.device,
            half=self.half,
            max_det=self.max_det,
            agnostic_nms=self.agnostic_nms,
            verbose=self.verbose,
        )

        if not results:
            return []

        r0 = results[0]
        if r0.boxes is None or len(r0.boxes) == 0:
            return []

        # Convert tensors -> numpy
        xyxy = r0.boxes.xyxy.detach().cpu().numpy()  # (N, 4)
        conf = r0.boxes.conf.detach().cpu().numpy()  # (N,)
        cls = r0.boxes.cls.detach().cpu().numpy()    # (N,)

        dets: List[VehicleDet] = []
        for i in range(xyxy.shape[0]):
            x1, y1, x2, y2 = xyxy[i]
            b = (int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))
            b = _clamp_bbox_xyxy(b, w=w, h=h)
            if b is None:
                continue
            dets.append(VehicleDet(bbox=b, conf=float(conf[i]), cls=int(cls[i])))

        return dets


# Optional convenience factory so main.py stays clean
def make_vehicle_detector_from_config(cfg: dict) -> VehicleDetector:
    return VehicleDetector(
        model_path=cfg["model_path"],
        conf=cfg.get("conf", 0.35),
        iou=cfg.get("iou", 0.5),
        classes=cfg.get("classes"),
        imgsz=cfg.get("imgsz", 640),
        device=cfg.get("device"),
        half=cfg.get("half", False),
        max_det=cfg.get("max_det", 300),
        agnostic_nms=cfg.get("agnostic_nms", False),
        verbose=cfg.get("verbose", False),
    )