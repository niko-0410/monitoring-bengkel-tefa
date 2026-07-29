# Monitoring Bengkel TEFA

Sistem monitoring keselamatan kerja bengkel menggunakan YOLOv8 untuk deteksi APD (Alat Pelindung Diri) dan Safety Area.

## Fitur
- Deteksi APD: Helm Safety, Sarung Tangan Safety, Sepatu Safety
- Deteksi Safety Area (Restricted Zone)
- Buzzer alarm & lampu indikator (hijau/merah/kuning)
- Push notification Telegram
- Dashboard web real-time

## Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

```linux
source .venv/bin/activate
```

Buka http://localhost:5000
