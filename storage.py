import sqlite3
import os
from datetime import datetime


class Storage:
    DB_PATH = os.path.join('data', 'monitoring.db')

    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS apd_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                helm TEXT DEFAULT 'Tidak Terdeteksi',
                sepatu TEXT DEFAULT 'Tidak Terdeteksi',
                sarungtangan TEXT DEFAULT 'Tidak Terdeteksi',
                status TEXT DEFAULT 'Tidak Lengkap',
                keterangan TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS area_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'Aman',
                jarak TEXT DEFAULT '-',
                keterangan TEXT,
                notifikasi TEXT DEFAULT 'Tidak Dikirim'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telegram_config (
                feature TEXT PRIMARY KEY,
                bot_token TEXT,
                chat_id TEXT
            )
        ''')
        self.conn.commit()

    def add_apd_log(self, helm, sepatu, sarungtangan, status, keterangan=''):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO apd_logs (timestamp, helm, sepatu, sarungtangan, status, keterangan) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (now, helm, sepatu, sarungtangan, status, keterangan)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_area_log(self, status, jarak='-', keterangan='', notifikasi='Tidak Dikirim'):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO area_logs (timestamp, status, jarak, keterangan, notifikasi) '
            'VALUES (?, ?, ?, ?, ?)',
            (now, status, jarak, keterangan, notifikasi)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_apd_logs(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM apd_logs ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_area_logs(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM area_logs ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_apd_logs_today(self):
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM apd_logs WHERE timestamp LIKE ? ORDER BY id DESC', (f'{today}%',))
        return [dict(row) for row in cursor.fetchall()]

    def get_area_logs_today(self):
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM area_logs WHERE timestamp LIKE ? ORDER BY id DESC', (f'{today}%',))
        return [dict(row) for row in cursor.fetchall()]

    def get_alarm_count_today(self):
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM apd_logs WHERE timestamp LIKE ? AND status = 'Tidak Lengkap'",
            (f'{today}%',)
        )
        apd_count = cursor.fetchone()['count']
        cursor.execute(
            "SELECT COUNT(*) as count FROM area_logs WHERE timestamp LIKE ? AND status = 'Bahaya'",
            (f'{today}%',)
        )
        area_count = cursor.fetchone()['count']
        return apd_count + area_count

    def get_entry_count_today(self):
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM apd_logs WHERE timestamp LIKE ?', (f'{today}%',))
        apd_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) as count FROM area_logs WHERE timestamp LIKE ?', (f'{today}%',))
        area_count = cursor.fetchone()['count']
        return apd_count + area_count

    def save_telegram_config(self, feature, bot_token, chat_id):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO telegram_config (feature, bot_token, chat_id) VALUES (?, ?, ?)',
            (feature, bot_token, chat_id)
        )
        self.conn.commit()

    def get_telegram_config(self, feature):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM telegram_config WHERE feature = ?', (feature,))
        row = cursor.fetchone()
        return dict(row) if row else {'bot_token': '', 'chat_id': ''}

    def clear_apd_logs(self):
        self.conn.cursor().execute('DELETE FROM apd_logs')
        self.conn.commit()

    def clear_area_logs(self):
        self.conn.cursor().execute('DELETE FROM area_logs')
        self.conn.commit()
