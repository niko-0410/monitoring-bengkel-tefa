# SUMMARY

## Objective
Build a **Monitoring Sistem Bengkel TEFA** web application using Python Flask + YOLOv8 for detecting PPE (APD) compliance in a workshop environment.

## 3 Detection Modes
| Mode | Model | Required Classes |
|---|---|---|
| `model_3class` | `models/apd_custom_best.pt` (YOLO) | **Helm Safety**, **sarung tangan safety**, **sepatu safety** |
| `model_6class` | `models/ppe_6class.onnx` (YOLO ONNX) | **Gloves**, **helmet** |
| `algorithm` | None (CV color+contour) | **Helm Safety**, **sepatu safety**, **sarung tangan safety** |

## Architecture
- **`detection/apd_detector.py`** — Core: background capture thread, 3 detection modes via `MODEL_CONFIGS`, 95% confidence threshold, buzzer (1x beep when ALL safe), indicator (hijau/merah/kuning)
- **`detection/safety_area.py`** — Safety area detection (unchanged)
- **`models/`** — `apd_custom_best.pt` (custom 3-class), `ppe_6class.onnx` (reference PPE 6-class), `ppe_6class.pt` (PyTorch copy)
- **`app.py`** — Flask server: start/stop/status/stream endpoints, mode-aware model loading
- **`templates/index.html`** — Mode selector (3 options), dynamic check items, camera dropdown with `used_by` disables
- **`static/js/app.js`** — Dynamic `updateAPDUI(s)` iterating `s.items`, mode selector, camera disable, polling

## Key Logic
- **Items status**: `_detect_model` populates `items` dict with all class names; `get_status` filters by `required_classes` (or all if empty)
- **Status** = `Lengkap` iff ALL required items are True
- **Buzzer**: 1x 200ms beep on transition to ALL safe
- **Indicator**: kuning (standby), merah (unsafe), hijau (safe)
- **Camera scan**: probes indices 0-9 via DirectShow, names from `Get-PnpDevice -Class Camera,Image`
- **Background thread**: `_capture_loop` reads camera → runs inference → stores JPEG+status in buffer; HTTP stream reads buffer without blocking

## Test Results (3/3/25)
- `get_status` correctly computes `Lengkap`/`Tidak Lengkap` for all 3 modes
- Model loading works for both `.pt` (3-class) and `.onnx` (6-class)
- Camera scan detects HP True Vision FHD Camera at index 0
- All Python code compiles without errors
