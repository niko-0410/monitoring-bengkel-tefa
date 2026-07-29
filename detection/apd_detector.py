import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
import threading
import sys
import traceback

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
    Deteksi APD dengan 3 mode:
      - model_3class: YOLO custom 3-class (Helm, Sarung Tangan, Sepatu)
      - model_6class: YOLO PPE 6-class (Gloves, Vest, goggles, helmet, mask, safety_shoe)
      - algorithm:   CV color-based detection
    """

    MODEL_CONFIGS = {
        'model_3class': {
            'class_names': {0: 'Helm Safety', 1: 'sarung tangan safety', 2: 'sepatu safety'},
            'class_colors': {0: (0, 255, 0), 1: (0, 200, 255), 2: (255, 165, 0)},
            'required_classes': [0, 1, 2],
            'model_path': 'models/apd_custom_best.pt',
            'label': 'YOLO 3-class (Custom)',
        },
        'model_6class': {
            'class_names': {0: 'Gloves', 1: 'Vest', 2: 'goggles', 3: 'helmet', 4: 'mask', 5: 'safety_shoe'},
            'class_colors': {0: (0, 255, 0), 1: (0, 200, 255), 2: (0, 200, 255), 3: (0, 255, 0), 4: (0, 200, 255), 5: (0, 200, 255)},
            'required_classes': [0, 3],
            'model_path': 'models/ppe_6class.onnx',
            'label': 'YOLO 6-class (PPE)',
        },
    }

    def __init__(self):
        self.model = None
        self.models_loaded = False
        self.confidence_threshold = 0.45
        self.cap = None
        self.is_running = False
        self.camera_id = 0
        self.detection_mode = 'model_3class'
        self.class_names = {}
        self.class_colors = {}
        self.required_classes = []
        self.buzzer = BuzzerAlarm()
        self._safety_beep_given = False
        self._capture_thread = None
        self._capture_running = False
        self._frame_lock = threading.Lock()
        self._latest_jpeg = None
        self._latest_status = None
        self.last_result = {
            'items': {},
            'detections': [],
            'timestamp': None
        }
        self._init_model_config('model_3class')

    def _init_model_config(self, mode):
        if mode in self.MODEL_CONFIGS:
            cfg = self.MODEL_CONFIGS[mode]
            self.class_names = cfg['class_names'].copy()
            self.class_colors = cfg['class_colors'].copy()
            self.required_classes = cfg['required_classes'].copy()
        else:
            self.class_names = {}
            self.class_colors = {}
            self.required_classes = []

    @staticmethod
    def _enhance_brightness(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg = gray.mean()
        if avg < 100:
            alpha = min(100.0 / max(avg, 1), 4.0)
            beta = int((100 - avg) * 0.5)
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        return frame

    def _detect_algorithm(self, frame):
        h, w = frame.shape[:2]
        enhanced = self._enhance_brightness(frame)
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
        detections = []

        upper = hsv[0:int(h * 0.35), :]
        lower = hsv[int(h * 0.7):, :]
        mid_left = hsv[int(h * 0.3):int(h * 0.7), 0:int(w * 0.3)]
        mid_right = hsv[int(h * 0.3):int(h * 0.7), int(w * 0.7):]

        helm_found = False
        helm_conf = 0.0
        lower_white = np.array([0, 0, 150])
        upper_white = np.array([180, 60, 255])
        mask_white = cv2.inRange(upper, lower_white, upper_white)
        contours_w, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_w:
            area = cv2.contourArea(cnt)
            if area > 2000:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = cw / max(ch, 1)
                if 0.5 < aspect < 2.0:
                    cv2.rectangle(frame, (x, y), (x + cw, y + ch), (0, 255, 0), 2)
                    cv2.putText(frame, 'Helm Safety', (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    detections.append({'class': 'Helm Safety', 'confidence': 0.7, 'bbox': [x, y, x + cw, y + ch], 'required': True})
                    helm_found = True
                    helm_conf = 0.7
                    break

        sepatu_found = False
        sepatu_conf = 0.0
        lower_dark = np.array([0, 0, 0])
        upper_dark = np.array([180, 255, 60])
        mask_dark = cv2.inRange(lower, lower_dark, upper_dark)
        contours_d, _ = cv2.findContours(mask_dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_d:
            area = cv2.contourArea(cnt)
            if area > 1500:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = cw / max(ch, 1)
                if 0.8 < aspect < 3.0:
                    cv2.rectangle(frame, (x, y + int(h * 0.7)), (x + cw, y + ch + int(h * 0.7)), (255, 165, 0), 2)
                    cv2.putText(frame, 'Sepatu Safety', (x, y + int(h * 0.7) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                    detections.append({'class': 'sepatu safety', 'confidence': 0.65, 'bbox': [x, y + int(h * 0.7), x + cw, y + ch + int(h * 0.7)], 'required': True})
                    sepatu_found = True
                    sepatu_conf = 0.65
                    break

        sarung_found = False
        sarung_conf = 0.0
        lower_glove = np.array([0, 0, 100])
        upper_glove = np.array([30, 80, 200])
        for region in [mid_left, mid_right]:
            if region.size == 0:
                continue
            mask_glove = cv2.inRange(region, lower_glove, upper_glove)
            contours_g, _ = cv2.findContours(mask_glove, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours_g:
                area = cv2.contourArea(cnt)
                if area > 800:
                    sarung_found = True
                    sarung_conf = 0.6
                    break
            if sarung_found:
                break

        if sarung_found:
            cv2.putText(frame, 'Sarung Tangan Safety', (10, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            detections.append({'class': 'sarung tangan safety', 'confidence': 0.6, 'bbox': [0, 0, 0, 0], 'required': True})

        th = 0.5
        self.last_result = {
            'items': {'Helm Safety': helm_found and helm_conf >= th, 'sepatu safety': sepatu_found and sepatu_conf >= th, 'sarung tangan safety': sarung_found and sarung_conf >= th},
            'detections': detections,
            'timestamp': time.time()
        }
        self._handle_buzzer()
        return {'frame': frame, 'result': self.last_result}

    def _detect_model(self, frame):
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
                if cls_id not in self.class_names:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                is_required = cls_id in self.required_classes
                color = self.class_colors.get(cls_id, (0, 255, 0))
                label = self.class_names[cls_id]

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
        items = {}
        for cls_id in self.class_names:
            name = self.class_names[cls_id]
            is_req = cls_id in self.required_classes
            if is_req:
                items[name] = cls_id in detected_classes and class_confidences.get(cls_id, 0) >= confidence_threshold
            else:
                items[name] = cls_id in detected_classes

        self.last_result = {
            'items': items,
            'detections': detections,
            'timestamp': time.time()
        }

        self._handle_buzzer()
        return {'frame': frame, 'result': self.last_result}

    def _get_mode_label(self):
        if self.detection_mode == 'algorithm':
            return 'Algoritma CV'
        cfg = self.MODEL_CONFIGS.get(self.detection_mode, {})
        return cfg.get('label', 'Model')

    def load_model(self, mode='model_3class'):
        if self.models_loaded and self.detection_mode == mode:
            return True
        self.models_loaded = False
        self.model = None
        self.detection_mode = mode
        self._init_model_config(mode)
        cfg = self.MODEL_CONFIGS.get(mode)
        if not cfg:
            return False
        model_path = cfg['model_path']
        try:
            if not os.path.exists(model_path):
                print(f"[APD] Model not found at {model_path}")
                return False
            task = 'detect' if model_path.endswith('.onnx') else None
            self.model = YOLO(model_path, task=task)
            self.models_loaded = True
            print(f"[APD] {cfg['label']} loaded: {model_path}")
            return True
        except Exception as e:
            print(f"[APD] Model load error: {e}")
            return False

    @staticmethod
    def _get_camera_names_windows():
        import subprocess, json, re
        ps_script = '$devices = Get-PnpDevice -Class Camera,Image -Status OK; $devices | ForEach-Object { [PSCustomObject]@{Name=$_.FriendlyName; ID=$_.InstanceID} } | ConvertTo-Json -Compress'
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if not isinstance(data, list):
                    data = [data]
                names = []
                for d in data:
                    name = d.get("Name", "Unknown")
                    names.append(name)
                return names
        except Exception:
            pass
        return []

    @staticmethod
    def _get_camera_caps(source):
        try:
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ret, frame = cap.read()
                if ret:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap.release()
                    return f'{w}x{h}'
                cap.release()
        except Exception:
            pass
        return None

    def list_cameras(self):
        cameras = []
        wmi_names = self._get_camera_names_windows()
        probe_results = []
        for i in range(10):
            caps = self._get_camera_caps(i)
            probe_results.append(caps)

        for i, caps in enumerate(probe_results):
            if caps:
                name = wmi_names[i] if i < len(wmi_names) else f'USB Camera ({i})'
                cameras.append({'id': i, 'name': name, 'resolution': caps})

        if not cameras:
            cameras.append({'id': 0, 'name': 'Default Camera', 'resolution': '640x480'})
        return cameras

    def start_camera(self, camera_id=0, mode='model_3class'):
        if self.cap is not None and self.cap.isOpened():
            return True

        self.camera_id = camera_id
        self.detection_mode = mode
        self._init_model_config(mode)
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
        self._capture_running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        print(f"[APD] Camera {camera_id} started ({self._get_mode_label()})")
        return True

    def stop_camera(self):
        self._capture_running = False
        self.is_running = False
        self.buzzer.stop()
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _capture_loop(self):
        while self._capture_running and self.cap is not None:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                if self.detection_mode == 'algorithm':
                    result = self._detect_algorithm(frame)
                elif self.model is not None:
                    result = self._detect_model(frame)
                else:
                    result = {'frame': frame, 'result': self.last_result}

                _, jpeg = cv2.imencode('.jpg', result['frame'], [cv2.IMWRITE_JPEG_QUALITY, 80])
                with self._frame_lock:
                    self._latest_jpeg = jpeg.tobytes()
                    self._latest_status = result['result']
            except Exception as e:
                print(f"[APD] Capture loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

    def detect(self):
        if not self.is_running:
            return None
        with self._frame_lock:
            if self._latest_status is not None:
                self.last_result = self._latest_status
        return {'result': self.last_result}

    def get_frame_jpeg(self):
        if not self.is_running:
            return None, None
        with self._frame_lock:
            jpeg = self._latest_jpeg
            status = self._latest_status
        return jpeg, status

    def _handle_buzzer(self):
        items = self.last_result.get('items', {})
        required_names = [self.class_names[c] for c in self.required_classes if c in self.class_names] if self.required_classes else list(items.keys())
        required_items = {k: v for k, v in items.items() if k in required_names}
        all_safe = all(required_items.values()) if required_items else False

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

    def get_status(self):
        self.detect()
        items = self.last_result.get('items', {})
        required_names = [self.class_names[c] for c in self.required_classes if c in self.class_names] if self.required_classes else list(items.keys())
        required_items = {k: v for k, v in items.items() if k in required_names}
        all_safe = all(required_items.values()) if required_items else False

        if not self.is_running:
            indicator = 'kuning'
        elif all_safe:
            indicator = 'hijau'
        else:
            indicator = 'merah'

        if self.detection_mode == 'algorithm':
            mode_label = 'Algoritma CV'
        elif self.models_loaded:
            cfg = self.MODEL_CONFIGS.get(self.detection_mode, {})
            mode_label = cfg.get('label', 'Model')
        else:
            mode_label = 'Tidak Aktif'

        return {
            'items': items,
            'status': 'Lengkap' if all_safe else 'Tidak Lengkap',
            'is_safe': all_safe,
            'indicator': indicator,
            'detections': self.last_result['detections'],
            'is_running': self.is_running,
            'model_loaded': self.models_loaded,
            'detection_mode': self.detection_mode,
            'mode': mode_label,
            'camera_id': self.camera_id,
            'buzzer_active': self.buzzer.is_active
        }
