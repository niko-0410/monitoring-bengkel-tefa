# Monitoring Bengkel TEFA

Sistem monitoring keselamatan kerja bengkel menggunakan YOLOv8 untuk deteksi APD (Alat Pelindung Diri) dan Safety Area.

## Fitur
- Deteksi APD: Helm Safety, Sarung Tangan Safety, Sepatu Safety
- Deteksi Safety Area (Restricted Zone)
- Buzzer alarm & lampu indikator (hijau/merah/kuning)
- Push notification Telegram
- Dashboard web real-time

## Model Files

Model YOLO tidak disimpan di repository (ukuran besar). Download melalui GitHub Releases:

```bash
# Download otomatis (Linux / Git Bash)
bash download_models.sh

# Atau manual dari browser:
# https://github.com/niko-0410/monitoring-bengkel-tefa/releases/tag/models-v1
```

File yang didownload akan masuk ke folder `models/`:
- `apd_custom_best.pt` — Custom 3-class (Helm Safety, sarung tangan safety, sepatu safety)
- `ppe_6class.onnx` — Reference PPE 6-class (Gloves, Vest, goggles, helmet, mask, safety_shoe)
- `ppe_6class.pt` — PyTorch version of 6-class

## Setup

### Windows
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Buka http://localhost:5000

## Deteksi Mode

| Mode | Keterangan | Kelas Wajib |
|---|---|---|
| `model_3class` | YOLO 3-class custom | Helm Safety, sarung tangan safety, sepatu safety |
| `model_6class` | YOLO PPE 6-class ONNX | Gloves, helmet |
| `algorithm` | Color + contour (tanpa model) | Helm Safety, sepatu safety, sarung tangan safety |
