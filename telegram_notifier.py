import requests
import json
from datetime import datetime


class TelegramNotifier:
    def __init__(self, bot_token='', chat_id=''):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def update_config(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, message):
        if not self.bot_token or not self.chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            resp = requests.post(url, json=payload, timeout=10)
            return resp.json().get('ok', False)
        except Exception as e:
            print(f"[Telegram] Send error: {e}")
            return False

    def send_apd_alert(self, missing_items):
        now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        items_text = '\n'.join(f'- {item}' for item in missing_items)
        message = (
            f"&#9888; <b>ALERT KESELAMATAN APD</b> &#9888;\n\n"
            f"Waktu: {now}\n"
            f"Status: <b>TIDAK LENGKAP</b>\n\n"
            f"APD yang belum terdeteksi:\n{items_text}\n\n"
            f"Segera periksa kelengkapan APD petugas!"
        )
        return self.send_message(message)

    def send_safety_area_alert(self, distance, object_label):
        now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        message = (
            f"&#128680; <b>ALERT SAFETY AREA</b> &#128680;\n\n"
            f"Waktu: {now}\n"
            f"Status: <b>BAHAYA - OBJEK MASUK AREA TERLARANG</b>\n\n"
            f"Objek: {object_label}\n"
            f"Jarak: {distance}\n\n"
            f"Segera lakukan tindakan!"
        )
        return self.send_message(message)

    def send_test_message(self, feature):
        now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        message = (
            f"&#9989; <b>TEST NOTIFIKASI</b>\n\n"
            f"Waktu: {now}\n"
            f"Fitur: {feature}\n"
            f"Status: Koneksi Telegram berhasil!"
        )
        return self.send_message(message)
