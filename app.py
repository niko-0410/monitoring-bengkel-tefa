from flask import Flask, render_template, Response, jsonify, request
import time
import threading
from detection.apd_detector import APDDetector
from detection.safety_area import SafetyAreaDetector
from telegram_notifier import TelegramNotifier
from storage import Storage

app = Flask(__name__)

apd_detector = APDDetector()
safety_detector = SafetyAreaDetector()
storage = Storage()

tg_apd = TelegramNotifier()
tg_area = TelegramNotifier()

apd_alert_cooldown = 0
area_alert_cooldown = 0
ALERT_COOLDOWN_SECONDS = 10


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/apd/start', methods=['POST'])
def apd_start():
    data = request.json or {}
    camera_id = data.get('camera_id', 0)
    mode = data.get('mode', 'model_3class')

    if mode.startswith('model_'):
        if not apd_detector.load_model(mode=mode):
            return jsonify({'success': False, 'message': 'Gagal load model'}), 500
    elif mode == 'algorithm':
        apd_detector.models_loaded = False
        apd_detector.model = None
    else:
        return jsonify({'success': False, 'message': 'Mode tidak dikenal'}), 400

    if apd_detector.start_camera(camera_id, mode=mode):
        cfg = apd_detector.MODEL_CONFIGS.get(mode, {})
        label = cfg.get('label', 'Algoritma CV')
        return jsonify({'success': True, 'message': f'Kamera {camera_id} aktif ({label})'})
    return jsonify({'success': False, 'message': 'Gagal mengakses kamera'}), 500


@app.route('/api/apd/stop', methods=['POST'])
def apd_stop():
    apd_detector.stop_camera()
    return jsonify({'success': True, 'message': 'Kamera APD dihentikan'})


@app.route('/api/apd/status')
def apd_status():
    return jsonify(apd_detector.get_status())


@app.route('/api/apd/test-buzzer', methods=['POST'])
def apd_test_buzzer():
    data = request.json or {}
    mode = data.get('mode', 'danger')
    apd_detector.test_buzzer(mode)
    return jsonify({'success': True, 'message': f'Test buzzer {mode}'})


@app.route('/api/apd/stream')
def apd_stream():
    def generate():
        while apd_detector.is_running:
            jpeg, status = apd_detector.get_frame_jpeg()
            if jpeg is None:
                time.sleep(0.1)
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n\r\n')

            check_apd_alert(status)
            time.sleep(0.03)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/apd/logs')
def apd_logs():
    return jsonify(storage.get_apd_logs())


@app.route('/api/apd/logs/clear', methods=['POST'])
def apd_clear_logs():
    storage.clear_apd_logs()
    return jsonify({'success': True})


@app.route('/api/safety/start', methods=['POST'])
def safety_start():
    data = request.json or {}
    camera_id = data.get('camera_id', 0)
    if safety_detector.load_model() and safety_detector.start_camera(camera_id):
        return jsonify({'success': True, 'message': f'Kamera {camera_id} aktif (buzzer bawaan)'})
    return jsonify({'success': False, 'message': 'Gagal mengakses kamera'}), 500


@app.route('/api/safety/stop', methods=['POST'])
def safety_stop():
    safety_detector.stop_camera()
    return jsonify({'success': True, 'message': 'Kamera Safety Area dihentikan'})


@app.route('/api/safety/status')
def safety_status():
    return jsonify(safety_detector.get_status())


@app.route('/api/safety/test-buzzer', methods=['POST'])
def safety_test_buzzer():
    data = request.json or {}
    mode = data.get('mode', 'danger')
    safety_detector.test_buzzer(mode)
    return jsonify({'success': True, 'message': f'Test buzzer {mode}'})


@app.route('/api/safety/set-zone', methods=['POST'])
def safety_set_zone():
    data = request.json
    safety_detector.set_restricted_zone(data['x'], data['y'], data['w'], data['h'])
    return jsonify({'success': True, 'message': 'Area terlarang diatur'})


@app.route('/api/safety/reset-zone', methods=['POST'])
def safety_reset_zone():
    safety_detector.clear_restricted_zone()
    return jsonify({'success': True, 'message': 'Area terlarang direset'})


@app.route('/api/safety/stream')
def safety_stream():
    def generate():
        while safety_detector.is_running:
            jpeg, status = safety_detector.get_frame_jpeg()
            if jpeg is None:
                time.sleep(0.1)
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n\r\n')

            check_safety_alert(status)
            time.sleep(0.03)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/safety/logs')
def safety_logs():
    return jsonify(storage.get_area_logs())


@app.route('/api/safety/logs/clear', methods=['POST'])
def safety_clear_logs():
    storage.clear_area_logs()
    return jsonify({'success': True})


@app.route('/api/telegram/config', methods=['POST'])
def telegram_config():
    data = request.json
    feature = data.get('feature', 'apd')
    bot_token = data.get('bot_token', '')
    chat_id = data.get('chat_id', '')

    storage.save_telegram_config(feature, bot_token, chat_id)

    if feature == 'apd':
        tg_apd.update_config(bot_token, chat_id)
    else:
        tg_area.update_config(bot_token, chat_id)

    return jsonify({'success': True, 'message': 'Konfigurasi Telegram disimpan'})


@app.route('/api/telegram/config/<feature>')
def get_telegram_config(feature):
    config = storage.get_telegram_config(feature)
    return jsonify(config)


@app.route('/api/telegram/test', methods=['POST'])
def telegram_test():
    data = request.json
    feature = data.get('feature', 'APD')
    bot_token = data.get('bot_token', '')
    chat_id = data.get('chat_id', '')

    notifier = TelegramNotifier(bot_token, chat_id)
    ok = notifier.send_test_message(feature)
    return jsonify({'success': ok, 'message': 'Test berhasil' if ok else 'Test gagal'})


@app.route('/api/dashboard')
def dashboard():
    apd_today = storage.get_apd_logs_today()
    area_today = storage.get_area_logs_today()
    alarm_count = storage.get_alarm_count_today()
    entry_count = storage.get_entry_count_today()

    all_logs = []
    for log in apd_today[:5]:
        all_logs.append({
            'waktu': log['timestamp'],
            'fitur': 'Kelengkapan APD',
            'status': log['status'],
            'keterangan': log['keterangan']
        })
    for log in area_today[:5]:
        all_logs.append({
            'waktu': log['timestamp'],
            'fitur': 'Safety Area',
            'status': log['status'],
            'keterangan': log['keterangan']
        })
    all_logs.sort(key=lambda x: x['waktu'], reverse=True)

    import os
    ppe_model_exists = os.path.exists(os.path.join('models', 'apd_custom_best.pt'))

    return jsonify({
        'alarm_count': alarm_count,
        'entry_count': entry_count,
        'recent_logs': all_logs[:10],
        'apd_status': apd_detector.get_status(),
        'safety_status': safety_detector.get_status(),
        'model_info': {
            'ppe_model': ppe_model_exists,
            'ppe_model_path': 'models/apd_custom_best.pt',
            'ppe_model_classes': 'Helm Safety, Sarung Tangan Safety, Sepatu Safety',
            'safety_model': 'yolov8n.pt (COCO - 80 classes)'
        }
    })


def check_apd_alert(status):
    global apd_alert_cooldown
    if status is None or status.get('status') == 'Lengkap':
        apd_alert_cooldown = 0
        return

    now = time.time()
    if apd_alert_cooldown > 0 and (now - apd_alert_cooldown) < ALERT_COOLDOWN_SECONDS:
        return
    apd_alert_cooldown = now

    missing = []
    if not status.get('helm'):
        missing.append('Helm Safety')
    if not status.get('sepatu'):
        missing.append('Sepatu Safety')
    if not status.get('sarungtangan'):
        missing.append('Sarung Tangan')

    storage.add_apd_log(
        helm='Lengkap' if status.get('helm') else 'Tidak Lengkap',
        sepatu='Lengkap' if status.get('sepatu') else 'Tidak Lengkap',
        sarungtangan='Lengkap' if status.get('sarungtangan') else 'Tidak Lengkap',
        status='Tidak Lengkap',
        keterangan=f"Missing: {', '.join(missing)}"
    )

    config = storage.get_telegram_config('apd')
    if config.get('bot_token') and config.get('chat_id'):
        tg = TelegramNotifier(config['bot_token'], config['chat_id'])
        threading.Thread(target=tg.send_apd_alert, args=(missing,)).start()


def check_safety_alert(status):
    global area_alert_cooldown
    if status is None or not status.get('object_in_zone'):
        area_alert_cooldown = 0
        return

    now = time.time()
    if area_alert_cooldown > 0 and (now - area_alert_cooldown) < ALERT_COOLDOWN_SECONDS:
        return
    area_alert_cooldown = now

    distance = status.get('intrusion_distance', '-')
    obj = status.get('intrusion_object', 'Unknown')

    notif_status = 'Tidak Dikirim'
    config = storage.get_telegram_config('safety-area')
    if config.get('bot_token') and config.get('chat_id'):
        tg = TelegramNotifier(config['bot_token'], config['chat_id'])
        threading.Thread(target=tg.send_safety_area_alert, args=(distance, obj)).start()
        notif_status = 'Dikirim'

    storage.add_area_log(
        status='Bahaya',
        jarak=distance,
        keterangan=f'Objek "{obj}" mendekati area terlarang',
        notifikasi=notif_status
    )


def load_telegram_configs():
    config_apd = storage.get_telegram_config('apd')
    if config_apd.get('bot_token'):
        tg_apd.update_config(config_apd['bot_token'], config_apd['chat_id'])

    config_area = storage.get_telegram_config('safety-area')
    if config_area.get('bot_token'):
        tg_area.update_config(config_area['bot_token'], config_area['chat_id'])


@app.route('/api/cameras')
def list_cameras():
    cameras = apd_detector.list_cameras()
    apd_cam = apd_detector.camera_id if apd_detector.is_running else None
    area_cam = safety_detector.camera_id if safety_detector.is_running else None
    for cam in cameras:
        used_by = []
        if apd_cam == cam['id']:
            used_by.append('apd')
        if area_cam == cam['id']:
            used_by.append('safety')
        cam['used_by'] = used_by
    return jsonify({'cameras': cameras})


if __name__ == '__main__':
    load_telegram_configs()
    print("\n" + "=" * 50)
    print("  MONITORING SISTEM BENGKEL TEFA")
    print("  Kamera: HP True Vision FHD + USB Camera")
    print("  Alarm: Buzzer bawaan (PC speaker)")
    print("  Model: YOLOv8 Custom APD (3-class)")
    print("  Buka: http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
