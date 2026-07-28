import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
import threading
import sys

if sys.platform == 'win32':
    import winsound


class BuzzerAlarm:
    def __init__(self):
        self.is_active = False
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._buzzer_type = 'system' if sys.platform == 'win32' else 'system'

    def start_danger(self):
        with self._lock:
            if self.is_active:
                return
            self._stop_event.clear()
            self.is_active = True
            self._thread = threading.Thread(target=self._danger_loop, daemon=True)
            self._thread.start()

    def start_warning(self):
        with self._lock:
            if self.is_active:
                return
            self._stop_event.clear()
            self.is_active = True
            self._thread = threading.Thread(target=self._warning_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        with self._lock:
            self.is_active = False

    def beep_once(self, freq=1000, duration=200):
        if sys.platform == 'win32':
            try:
                winsound.Beep(freq, duration)
            except Exception:
                pass

    def _safe_beep(self, freq, duration):
        if self._stop_event.is_set():
            return False
        if sys.platform == 'win32':
            try:
                winsound.Beep(freq, duration)
            except Exception:
                pass
        return not self._stop_event.is_set()

    def _danger_loop(self):
        while not self._stop_event.is_set():
            if sys.platform == 'win32':
                try:
                    if not self._safe_beep(1000, 200):
                        break
                    if not self._safe_beep(800, 200):
                        break
                    if not self._safe_beep(1000, 200):
                        break
                except Exception:
                    pass
            time.sleep(0.3)

    def _warning_loop(self):
        while not self._stop_event.is_set():
            if sys.platform == 'win32':
                try:
                    if not self._safe_beep(600, 300):
                        break
                except Exception:
                    pass
            time.sleep(0.3)


class APDDetector:
    """
    Deteksi APD menggunakan YOLOv8 custom model (Roboflow 3-class dataset).
    Model mendeteksi langsung:
      - class 0: Helm Safety
      - class 1: sarung tangan safety
      - class 2: sepatu safety
    """

    CLASS_NAMES = {
        0: 'Helm Safety',
        1: 'sarung tangan safety',
        2: 'sepatu safety',
    }

    CLASS_COLORS = {
        0: (0, 255, 0),
        1: (0, 200, 255),
        2: (255, 165, 0),
    }

    REQUIRED_CLASSES = [0, 1, 2]

    def __init__(self):
        self.model = None
        self.models_loaded = False
        self.confidence_threshold = 0.15
        self.cap = None
        self.is_running = False
        self.camera_id = 0
        self.buzzer = BuzzerAlarm()
        self._safety_beep_given = False
        self.last_result = {
            'helm': False,
            'sepatu': False,
            'sarungtangan': False,
            'detections': [],
            'timestamp': None
        }

    @staticmethod
    def _enhance_brightness(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg = gray.mean()
        if avg < 100:
            alpha = min(100.0 / max(avg, 1), 4.0)
            beta = int((100 - avg) * 0.5)
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        return frame

    def load_model(self):
        if self.models_loaded:
            return True
        try:
            model_path = 'models/apd_custom_best.pt'
            if not os.path.exists(model_path):
                print(f"[APD] Model not found at {model_path}, falling back to yolov8n.pt")
                model_path = 'models/yolov8n.pt'
            self.model = YOLO(model_path)
            self.models_loaded = True
            print(f"[APD] Custom APD model loaded: {model_path}")
            return True
        except Exception as e:
            print(f"[APD] Model load error: {e}")
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
                print(f"[APD] Cannot open camera {camera_id}")
                return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.is_running = True
        print(f"[APD] Camera {camera_id} started (HP True Vision FHD - DirectShow)")
        return True

    def stop_camera(self):
        self.is_running = False
        self.buzzer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def detect(self):
        if not self.is_running or self.cap is None or not self.cap.isOpened():
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        if self.model is None:
            return {'frame': frame, 'result': self.last_result}

        enhanced = self._enhance_brightness(frame)
        results = self.model(enhanced, conf=self.confidence_threshold, verbose=False)

        detections = []
        detected_classes = set()
        class_confidences = {}

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in self.CLASS_NAMES:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                is_required = cls_id in self.REQUIRED_CLASSES
                color = self.CLASS_COLORS.get(cls_id, (0, 255, 0))
                label = self.CLASS_NAMES[cls_id]

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{label} {conf:.0%}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                detections.append({
                    'class': label,
                    'class_id': cls_id,
                    'confidence': round(conf, 2),
                    'bbox': [x1, y1, x2, y2],
                    'required': is_required
                })

                if is_required:
                    detected_classes.add(cls_id)
                    if cls_id not in class_confidences or conf > class_confidences[cls_id]:
                        class_confidences[cls_id] = conf

        confidence_threshold = 0.95
        helm_found = 0 in detected_classes and class_confidences.get(0, 0) >= confidence_threshold
        sepatu_found = 2 in detected_classes and class_confidences.get(2, 0) >= confidence_threshold
        sarungtangan_found = 1 in detected_classes and class_confidences.get(1, 0) >= confidence_threshold

        self.last_result = {
            'helm': helm_found,
            'sepatu': sepatu_found,
            'sarungtangan': sarungtangan_found,
            'detections': detections,
            'timestamp': time.time()
        }

        self._handle_buzzer()

        return {'frame': frame, 'result': self.last_result}

    def _handle_buzzer(self):
        all_safe = all([
            self.last_result['helm'],
            self.last_result['sepatu'],
            self.last_result['sarungtangan']
        ])

        if all_safe and not self._safety_beep_given:
            self.buzzer.beep_once(1000, 200)
            self._safety_beep_given = True
        elif not all_safe:
            self._safety_beep_given = False

    def test_buzzer(self, mode='danger'):
        if mode == 'danger':
            self.buzzer.start_danger()
            threading.Timer(1.5, self.buzzer.stop).start()
        elif mode == 'warning':
            self.buzzer.start_warning()
            threading.Timer(1.5, self.buzzer.stop).start()
        else:
            self.buzzer.beep_once(1000, 300)

    def get_frame_jpeg(self):
        result = self.detect()
        if result is None:
            return None, None
        frame = result['frame']
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes(), result['result']

    def get_status(self):
        all_safe = all([
            self.last_result['helm'],
            self.last_result['sepatu'],
            self.last_result['sarungtangan']
        ])

        if not self.is_running or not self.models_loaded:
            indicator = 'kuning'
        elif all_safe:
            indicator = 'hijau'
        else:
            indicator = 'merah'

        return {
            'helm': self.last_result['helm'],
            'sepatu': self.last_result['sepatu'],
            'sarungtangan': self.last_result['sarungtangan'],
            'status': 'Lengkap' if all_safe else 'Tidak Lengkap',
            'is_safe': all_safe,
            'indicator': indicator,
            'detections': self.last_result['detections'],
            'is_running': self.is_running,
            'model_loaded': self.models_loaded,
            'mode': 'YOLOv8 Custom APD (Roboflow)' if self.models_loaded else 'Tidak Aktif',
            'camera_id': self.camera_id,
            'buzzer_active': self.buzzer.is_active
        }
