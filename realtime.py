import time
import threading
from typing import Optional, Tuple

import cv2

from src.vehicleDetector import VehicleDetector
from src.plateDetector import PlateDetector 
from src.crop import crop_bbox


class LatestFrameGrabber:
    """Continuously grabs frames and keeps only the latest one (low-latency)."""

    def __init__(self, source=0, width=1280, height=720):
        # ---> PI FIX: Added cv2.CAP_V4L2 for Linux camera stability
        self.cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source}")

        # ---> PI FIX: Force MJPG compression and HD resolution
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # ---> PI FIX: Warm up the camera sensor to fix the yellow/blue tint
        print(f"Warming up camera {source}...")
        for _ in range(30):
            self.cap.read()
            time.sleep(0.01)
        print(f"Camera {source} ready!")

        self.lock = threading.Lock()
        self.frame = None
        self.ok = True
        self.stopped = False

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stopped:
            ok, frame = self.cap.read()
            with self.lock:
                self.ok = ok
                if ok:
                    self.frame = frame
            if not ok:
                time.sleep(0.01)  # avoid busy spin if source fails

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return True, self.frame.copy()

    def release(self):
        self.stopped = True
        self.thread.join(timeout=1.0)
        self.cap.release()


def draw_bbox(img, bbox, label: str = "", thickness: int = 2):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), thickness)
    if label:
        cv2.putText(
            img, label, (int(x1), max(0, int(y1) - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA
        )


def main():
   VEHICLE_MODEL = "models/vehicle/vehicle_detect_model_ncnn_model"
   PLATE_MODEL = "models/plates/plate_detect_model_ncnn_model"


   print("Loading AI Models...")
   vehicle_detector = VehicleDetector(
       model_path=VEHICLE_MODEL,
       conf=0.85,
       iou=0.5,
       imgsz=640,
   )


   plate_detector = PlateDetector(
       model_path=PLATE_MODEL,
       conf=0.85, # We can increase this later if it keeps hallucinating!
       iou=0.5,
       imgsz=416,  
       max_det=10,
   )


   # ---- Split Real-time Capture ----
   print("Initializing Overhead Camera (Vehicles)...")
   grabber_overhead = LatestFrameGrabber(source=0)


   print("Initializing Entrance Camera (Plates)...")
   # Change source=2 to source=1 if the NexiGo camera gives you an error!
   grabber_entrance = LatestFrameGrabber(source=2)


   fps_t0 = time.time()
   fps_count = 0
   fps = 0.0


   try:
       while True:
           # Grab the newest frames from BOTH cameras
           ok_over, frame_over = grabber_overhead.read()
           ok_ent, frame_ent = grabber_entrance.read()


           if not ok_over or frame_over is None or not ok_ent or frame_ent is None:
               continue


           # ==========================================
           # TASK 1: Overhead Camera -> Vehicles ONLY
           # ==========================================
           vehicles = vehicle_detector.detect(frame_over)
          
           for v in vehicles:
                # Calculate the size (area) of the box
                x1, y1, x2, y2 = v.bbox
                area = (x2 - x1) * (y2 - y1)
                
                # Only draw the box if it's big enough to be a real car (e.g., > 8000 pixels)
                if area > 30000:
                    draw_bbox(frame_over, v.bbox, label=f"veh {v.cls} {v.conf:.2f}")


           # ==========================================
           # TASK 2: Entrance Camera -> Plates ONLY
           # ==========================================
           # We don't crop the car anymore. We just scan the whole entrance frame for plates.
           plates = plate_detector.detect(frame_ent)
          
           for p in plates:
                # You can also add an area filter here if it thinks tiny leaves are plates!
                px1, py1, px2, py2 = p.bbox
                p_area = (px2 - px1) * (py2 - py1)
                
                if p_area > 1000: # Adjust this number if plates are still hallucinating
                    draw_bbox(frame_ent, p.bbox, label=f"plate {p.conf:.2f}", thickness=3)


           # ---- FPS counter ----
           fps_count += 1
           now = time.time()
           if now - fps_t0 >= 1.0:
               fps = fps_count / (now - fps_t0)
               fps_t0 = now
               fps_count = 0


           # Draw FPS on both frames
           cv2.putText(frame_over, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
           cv2.putText(frame_ent, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)


           # ---- Show BOTH windows ----
           cv2.imshow("Overhead View - Vehicles", frame_over)
           cv2.imshow("Entrance View - Plates", frame_ent)


           key = cv2.waitKey(1) & 0xFF
           if key == ord("q") or key == 27: 
               print("Quit signal received. Shutting down cleanly...")
               break


   finally:
       # Make sure we clean up BOTH cameras
       grabber_overhead.release()
       grabber_entrance.release()
       cv2.destroyAllWindows()




if __name__ == "__main__":
   main()