import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
import math
import threading
import sys

if sys.platform == 'win32':
    import winsound


class BuzzerAlarm:
    def __init__(self):
        self.is_active = False
        self._thread = None
        self._stop_event = threading.Event()

    def start_danger(self):
        if self.is_active:
            return
        self._stop_event.clear()
        self.is_active = True
        self._thread = threading.Thread(target=self._danger_loop, daemon=True)
        self._thread.start()

    def start_warning(self):
        if self.is_active:
            return
        self._stop_event.clear()
        self.is_active = True
        self._thread = threading.Thread(target=self._warning_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.is_active = False
        if sys.platform == 'win32':
            try:
                winsound.Beep(0, 0)
            except Exception:
                pass

    def beep_once(self, freq=1000, duration=200):
        if sys.platform == 'win32':
            try:
                winsound.Beep(freq, duration)
            except Exception:
                pass

    def _danger_loop(self):
        while not self._stop_event.is_set():
            if sys.platform == 'win32':
                try:
                    winsound.Beep(1200, 150)
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.08)
                    winsound.Beep(900, 150)
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.08)
                    winsound.Beep(1200, 150)
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.4)
                except Exception:
                    time.sleep(0.5)
            else:
                time.sleep(0.5)

    def _warning_loop(self):
        while not self._stop_event.is_set():
            if sys.platform == 'win32':
                try:
                    winsound.Beep(600, 300)
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.6)
                except Exception:
                    time.sleep(0.5)
            else:
                time.sleep(0.5)


class SafetyAreaDetector:
    """
    Safety Area Detector:
    - Kamera bawaan laptop (webcam, camera_id=0)
    - Buzzer bawaan laptop (winsound.Beep via PC speaker)
    - YOLOv8 Detection untuk deteksi objek masuk area terlarang
    """

    def __init__(self):
        self.model = None
        self.model_path = os.path.join('models', 'yolov8n.pt')
        self.confidence_threshold = 0.35
        self.cap = None
        self.is_running = False
        self.camera_id = 0
        self.restricted_zone = None
        self.warning_distance = 100
        self.min_distance_meters = 1.0
        self.pixels_per_meter = 100
        self.buzzer = BuzzerAlarm()
        self.last_result = {
            'object_in_zone': False,
            'intrusion_object': '',
            'intrusion_distance': '',
            'detections': [],
            'timestamp': None
        }

    def load_model(self):
        if self.model is not None:
            return True
        try:
            print("[SafetyArea] Loading YOLOv8 detection model...")
            self.model = YOLO(self.model_path)
            print(f"[SafetyArea] Model loaded: {self.model_path}")
            return True
        except Exception as e:
            print(f"[SafetyArea] Model load error: {e}")
            return False

    @staticmethod
    def _get_camera_name(index):
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName'],
                capture_output=True, text=True, timeout=3
            )
            names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
            if index < len(names):
                return names[index]
        except Exception:
            pass
        default_names = {0: 'HP True Vision FHD Camera', 1: 'Jabra USB Camera'}
        return default_names.get(index, f'USB Camera ({index})')

    def list_cameras(self):
        cameras = []
        for i in range(6):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    ret, frame = cap.read()
                    if ret:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        name = self._get_camera_name(i)
                        cameras.append({'id': i, 'name': name, 'resolution': f'{w}x{h}'})
                    cap.release()
            except Exception:
                pass
        if not cameras:
            cameras.append({'id': 0, 'name': 'HP True Vision FHD Camera', 'resolution': '640x480'})
        return cameras

    def start_camera(self, camera_id=0):
        if self.cap is not None and self.cap.isOpened():
            return True

        self.camera_id = camera_id
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(camera_id)
            if not self.cap.isOpened():
                print(f"[SafetyArea] Cannot open camera {camera_id}")
                return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.is_running = True
        print(f"[SafetyArea] Camera {camera_id} started (DirectShow)")
        return True

    def stop_camera(self):
        self.is_running = False
        self.buzzer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def set_restricted_zone(self, x, y, w, h):
        self.restricted_zone = {'x': x, 'y': y, 'w': w, 'h': h}

    def clear_restricted_zone(self):
        self.restricted_zone = None
        self.buzzer.stop()
        self.last_result = {
            'object_in_zone': False,
            'intrusion_object': '',
            'intrusion_distance': '',
            'detections': [],
            'timestamp': None
        }

    def detect(self):
        if not self.is_running or self.cap is None or not self.cap.isOpened():
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        detections = []
        intrusion_detected = False
        intrusion_object = ''
        intrusion_distance = ''

        if self.restricted_zone and self.model:
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)

            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        cls_name = result.names[cls_id]
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2

                        zx = self.restricted_zone['x']
                        zy = self.restricted_zone['y']
                        zw = self.restricted_zone['w']
                        zh = self.restricted_zone['h']

                        in_zone = (zx < cx < zx + zw and zy < cy < zy + zh)

                        expanded_x = zx - self.warning_distance
                        expanded_y = zy - self.warning_distance
                        expanded_w = zw + self.warning_distance * 2
                        expanded_h = zh + self.warning_distance * 2

                        near_zone = (expanded_x < cx < expanded_x + expanded_w and
                                     expanded_y < cy < expanded_y + expanded_h)

                        dist_to_zone = self._distance_to_zone(cx, cy)
                        dist_meters = dist_to_zone / self.pixels_per_meter

                        detections.append({
                            'class': cls_name,
                            'confidence': round(conf, 2),
                            'bbox': [x1, y1, x2, y2],
                            'in_zone': in_zone,
                            'near_zone': near_zone,
                            'distance': round(dist_meters, 2)
                        })

                        if in_zone or near_zone:
                            color = (0, 0, 255) if in_zone else (0, 165, 255)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            label = f"{'BAHAYA' if in_zone else 'PERINGATAN'} {cls_name}"
                            cv2.putText(frame, label, (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                            if in_zone or dist_meters < self.min_distance_meters:
                                intrusion_detected = True
                                intrusion_object = cls_name
                                intrusion_distance = f"{dist_meters:.1f}m"
                        else:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{cls_name} {conf:.0%}", (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        self._draw_zone_overlay(frame)

        self.last_result = {
            'object_in_zone': intrusion_detected,
            'intrusion_object': intrusion_object,
            'intrusion_distance': intrusion_distance,
            'detections': detections,
            'timestamp': time.time()
        }

        self._handle_buzzer(intrusion_detected)

        return {'frame': frame, 'result': self.last_result}

    def _handle_buzzer(self, intrusion_detected):
        if intrusion_detected:
            if not self.buzzer.is_active:
                self.buzzer.start_danger()
        else:
            self.buzzer.stop()

    def test_buzzer(self, mode='danger'):
        if mode == 'danger':
            self.buzzer.start_danger()
            threading.Timer(1.5, self.buzzer.stop).start()
        elif mode == 'warning':
            self.buzzer.start_warning()
            threading.Timer(1.5, self.buzzer.stop).start()
        else:
            self.buzzer.beep_once(1000, 300)

    def _distance_to_zone(self, px, py):
        zx = self.restricted_zone['x']
        zy = self.restricted_zone['y']
        zw = self.restricted_zone['w']
        zh = self.restricted_zone['h']

        dx = max(0, max(zx - px, px - (zx + zw)))
        dy = max(0, max(zy - py, py - (zy + zh)))

        return math.sqrt(dx * dx + dy * dy)

    def _draw_zone_overlay(self, frame):
        if not self.restricted_zone:
            return

        zx = self.restricted_zone['x']
        zy = self.restricted_zone['y']
        zw = self.restricted_zone['w']
        zh = self.restricted_zone['h']

        overlay = frame.copy()
        cv2.rectangle(overlay, (zx, zy), (zx + zw, zy + zh), (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)

        cv2.rectangle(frame, (zx, zy), (zx + zw, zy + zh), (0, 0, 255), 3)
        cv2.putText(frame, 'AREA TERLARANG', (zx + 6, zy + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.rectangle(frame,
                      (zx - self.warning_distance, zy - self.warning_distance),
                      (zx + zw + self.warning_distance, zy + zh + self.warning_distance),
                      (0, 255, 255), 2)
        cv2.putText(frame, 'Zona Peringatan (1m)',
                    (zx - self.warning_distance + 4, zy - self.warning_distance - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    def get_frame_jpeg(self):
        result = self.detect()
        if result is None:
            return None, None
        frame = result['frame']
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes(), result['result']

    def get_status(self):
        return {
            'object_in_zone': self.last_result['object_in_zone'],
            'intrusion_object': self.last_result['intrusion_object'],
            'intrusion_distance': self.last_result['intrusion_distance'],
            'detections': self.last_result['detections'],
            'zone_set': self.restricted_zone is not None,
            'zone': self.restricted_zone,
            'is_running': self.is_running,
            'camera_id': self.camera_id,
            'buzzer_active': self.buzzer.is_active
        }
