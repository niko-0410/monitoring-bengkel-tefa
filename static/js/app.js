const App = {
    currentPage: 'dashboard',
    apdPolling: null,
    areaPolling: null,
    dashboardPolling: null,
    isDrawingZone: false,
    zoneStart: null,

    init() {
        this.setupNavigation();
        this.updateClock();
        setInterval(() => this.updateClock(), 1000);

        this.setupAPDControls();
        this.setupSafetyControls();
        this.setupTelegramConfigs();
        this.setupZoneDrawing();
        this.loadDashboard();
        this.loadTelegramConfigs();
        this.loadCameras();

        this.dashboardPolling = setInterval(() => this.loadDashboard(), 5000);
    },

    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                this.navigateTo(item.getAttribute('data-page'));
            });
        });
    },

    navigateTo(page) {
        this.currentPage = page;
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.getAttribute('data-page') === page);
        });
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(`page-${page}`).classList.add('active');

        const titles = {
            'dashboard': 'Dashboard',
            'apd': 'Kelengkapan Alat Pelindung Diri',
            'safety-area': 'Safety Area - Lingkungan Bengkel'
        };
        document.getElementById('page-title').textContent = titles[page] || 'Dashboard';

        if (page === 'dashboard') this.loadDashboard();
    },

    updateClock() {
        const now = new Date();
        document.getElementById('current-time').textContent = now.toLocaleString('id-ID', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    },

    // ========== APD ==========
    setupAPDControls() {
        document.getElementById('btn-start-apd').addEventListener('click', () => this.startAPD());
        document.getElementById('btn-stop-apd').addEventListener('click', () => this.stopAPD());
        document.getElementById('btn-clear-apd-log').addEventListener('click', () => this.clearAPDLogs());
        document.getElementById('btn-test-buzzer-apd').addEventListener('click', () => this.testBuzzer('apd'));
    },

    async startAPD() {
        try {
            const cameraId = parseInt(document.getElementById('apd-camera-select').value) || 0;
            const res = await fetch('/api/apd/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_id: cameraId })
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('apd-video').src = '/api/apd/stream';
                document.getElementById('apd-overlay').classList.add('hidden');
                document.getElementById('btn-start-apd').disabled = true;
                document.getElementById('btn-stop-apd').disabled = false;
                this.apdPolling = setInterval(() => this.pollAPDStatus(), 1000);
                this.showToast(`Kamera ${cameraId} aktif (buzzer bawaan)`, 'success');
                this.loadCameras();
            } else {
                this.showToast(data.message, 'error');
            }
        } catch (e) {
            this.showToast('Gagal mengakses kamera', 'error');
        }
    },

    async stopAPD() {
        await fetch('/api/apd/stop', { method: 'POST' });
        document.getElementById('apd-video').src = '';
        document.getElementById('apd-overlay').classList.remove('hidden');
        document.getElementById('btn-start-apd').disabled = false;
        document.getElementById('btn-stop-apd').disabled = true;
        if (this.apdPolling) { clearInterval(this.apdPolling); this.apdPolling = null; }
        this.resetAPDUI();
        this.showToast('Kamera APD dihentikan', 'info');
        this.loadCameras();
    },

    async pollAPDStatus() {
        try {
            const res = await fetch('/api/apd/status');
            const s = await res.json();
            this.updateAPDUI(s);
        } catch (e) { }
    },

    updateAPDUI(s) {
        this.updateCheckItem('helm', s.helm);
        this.updateCheckItem('sepatu', s.sepatu);
        this.updateCheckItem('sarung', s.sarungtangan);

        this.updateDashAPD('dash-helm', s.helm);
        this.updateDashAPD('dash-sepatu', s.sepatu);
        this.updateDashAPD('dash-sarung', s.sarungtangan);

        const circle = document.getElementById('apd-indicator-circle');
        const text = document.getElementById('apd-indicator-text');
        const badge = document.getElementById('apd-badge');
        const statEl = document.getElementById('stat-apd');

        if (s.status === 'Lengkap') {
            circle.className = 'indicator-circle safe';
            text.textContent = 'AMAN';
            this.setLamp('apd', 'green');
            badge.textContent = 'Lengkap';
            badge.className = 'panel-badge safe';
            statEl.textContent = 'Lengkap';
            statEl.className = 'status-safe';
        } else if (s.helm || s.sepatu || s.sarungtangan) {
            circle.className = 'indicator-circle danger';
            text.textContent = 'TIDAK AMAN';
            this.setLamp('apd', 'red');
            badge.textContent = 'Tidak Lengkap';
            badge.className = 'panel-badge danger';
            statEl.textContent = 'Tidak Lengkap';
            statEl.className = 'status-danger';
        } else {
            circle.className = 'indicator-circle standby';
            text.textContent = 'STANDBY';
            this.setLamp('apd', 'yellow');
        }
    },

    resetAPDUI() {
        ['helm', 'sepatu', 'sarung'].forEach(item => {
            const el = document.getElementById(`check-${item}`);
            el.className = 'check-item';
            document.getElementById(`${item}-icon`).innerHTML = '&#10060;';
            const st = document.getElementById(`${item}-status`);
            st.textContent = 'Belum Terdeteksi';
            st.className = 'check-status';
        });
        document.getElementById('apd-indicator-circle').className = 'indicator-circle standby';
        document.getElementById('apd-indicator-text').textContent = 'STANDBY';
        document.getElementById('apd-badge').textContent = 'Menunggu';
        document.getElementById('apd-badge').className = 'panel-badge';
        document.getElementById('stat-apd').textContent = '-';
        this.setLamp('apd', 'none');
    },

    updateCheckItem(item, detected) {
        const el = document.getElementById(`check-${item}`);
        const icon = document.getElementById(`${item}-icon`);
        const st = document.getElementById(`${item}-status`);
        if (detected) {
            el.className = 'check-item safe';
            icon.innerHTML = '&#9989;';
            st.textContent = 'Terdeteksi';
            st.className = 'check-status safe';
        } else {
            el.className = 'check-item unsafe';
            icon.innerHTML = '&#10060;';
            st.textContent = 'Tidak Terdeteksi';
            st.className = 'check-status unsafe';
        }
    },

    updateDashAPD(id, detected) {
        const el = document.getElementById(id);
        if (!el) return;
        const s = el.querySelector('.apd-status');
        s.textContent = detected ? 'Terdeteksi' : 'Tidak Terdeteksi';
        s.className = detected ? 'apd-status detected' : 'apd-status not-detected';
    },

    async clearAPDLogs() {
        await fetch('/api/apd/logs/clear', { method: 'POST' });
        document.getElementById('apd-log-body').innerHTML = '<tr><td colspan="6" class="empty-state">Belum ada riwayat</td></tr>';
        this.showToast('Riwayat APD dihapus', 'info');
    },

    // ========== SAFETY AREA ==========
    setupSafetyControls() {
        document.getElementById('btn-start-area').addEventListener('click', () => this.startSafety());
        document.getElementById('btn-stop-area').addEventListener('click', () => this.stopSafety());
        document.getElementById('btn-set-zone').addEventListener('click', () => this.enableZoneDraw());
        document.getElementById('btn-reset-zone').addEventListener('click', () => this.resetZone());
        document.getElementById('btn-clear-area-log').addEventListener('click', () => this.clearAreaLogs());
        document.getElementById('btn-test-buzzer-area').addEventListener('click', () => this.testBuzzer('safety-area'));
    },

    async startSafety() {
        try {
            const cameraId = parseInt(document.getElementById('area-camera-select').value) || 0;
            const res = await fetch('/api/safety/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_id: cameraId })
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('area-video').src = '/api/safety/stream';
                document.getElementById('area-overlay').classList.add('hidden');
                document.getElementById('btn-start-area').disabled = true;
                document.getElementById('btn-stop-area').disabled = false;
                this.areaPolling = setInterval(() => this.pollSafetyStatus(), 1000);
                this.showToast(`Kamera ${cameraId} aktif (buzzer bawaan)`, 'success');
                this.loadCameras();
            } else {
                this.showToast(data.message, 'error');
            }
        } catch (e) {
            this.showToast('Gagal mengakses kamera', 'error');
        }
    },

    async stopSafety() {
        await fetch('/api/safety/stop', { method: 'POST' });
        document.getElementById('area-video').src = '';
        document.getElementById('area-overlay').classList.remove('hidden');
        document.getElementById('btn-start-area').disabled = false;
        document.getElementById('btn-stop-area').disabled = true;
        if (this.areaPolling) { clearInterval(this.areaPolling); this.areaPolling = null; }
        this.resetSafetyUI();
        this.showToast('Kamera Safety Area dihentikan', 'info');
        this.loadCameras();
    },

    async pollSafetyStatus() {
        try {
            const res = await fetch('/api/safety/status');
            const s = await res.json();
            this.updateSafetyUI(s);
        } catch (e) { }
    },

    updateSafetyUI(s) {
        const circle = document.getElementById('area-indicator-circle');
        const text = document.getElementById('area-indicator-text');
        const badge = document.getElementById('area-badge');
        const statEl = document.getElementById('stat-area');
        const dashIndicator = document.getElementById('dash-area-indicator');
        const dashAlarm = document.getElementById('dash-alarm-status');

        if (s.object_in_zone) {
            circle.className = 'indicator-circle danger';
            text.textContent = 'BAHAYA';
            this.setLamp('area', 'red');
            badge.textContent = 'Bahaya';
            badge.className = 'panel-badge danger';
            statEl.textContent = 'Bahaya';
            statEl.className = 'status-danger';
            document.getElementById('obj-distance').textContent = s.intrusion_distance;

            if (dashIndicator) {
                dashIndicator.querySelector('.indicator-light').className = 'indicator-light red';
                dashIndicator.querySelector('span').textContent = `Objek: ${s.intrusion_object} - ${s.intrusion_distance}`;
            }
            if (dashAlarm) {
                dashAlarm.textContent = 'AKTIF';
                dashAlarm.className = 'status-danger';
            }
        } else if (s.is_running) {
            circle.className = 'indicator-circle safe';
            text.textContent = 'AMAN';
            this.setLamp('area', 'green');
            badge.textContent = 'Aman';
            badge.className = 'panel-badge safe';
            statEl.textContent = 'Aman';
            statEl.className = 'status-safe';
            document.getElementById('obj-distance').textContent = '-';

            if (dashIndicator) {
                dashIndicator.querySelector('.indicator-light').className = 'indicator-light green';
                dashIndicator.querySelector('span').textContent = 'Tidak ada objek di area terlarang';
            }
            if (dashAlarm) {
                dashAlarm.textContent = 'Normal';
                dashAlarm.className = '';
            }
        }

        if (s.zone_set) {
            document.getElementById('zone-status').textContent = 'Area sudah diatur';
            document.getElementById('zone-status').className = 'status-safe';
        }
    },

    resetSafetyUI() {
        document.getElementById('area-indicator-circle').className = 'indicator-circle standby';
        document.getElementById('area-indicator-text').textContent = 'STANDBY';
        document.getElementById('area-badge').textContent = 'Aman';
        document.getElementById('area-badge').className = 'panel-badge safe';
        document.getElementById('stat-area').textContent = 'Aman';
        document.getElementById('obj-distance').textContent = '-';
        this.setLamp('area', 'none');
    },

    enableZoneDraw() {
        const img = document.getElementById('area-video');
        this.isDrawingZone = true;
        document.getElementById('zone-hint').textContent = 'Klik pada gambar kamera untuk set area...';
        this.showToast('Klik pada gambar kamera untuk menggambar area terlarang', 'info');

        const handler = (e) => {
            if (!this.isDrawingZone) return;
            const rect = img.getBoundingClientRect();
            const scaleX = img.naturalWidth / rect.width;
            const scaleY = img.naturalHeight / rect.height;
            const x = Math.round((e.clientX - rect.left) * scaleX);
            const y = Math.round((e.clientY - rect.top) * scaleY);
            const w = Math.round(rect.width * scaleX * 0.4);
            const h = Math.round(rect.height * scaleY * 0.4);

            fetch('/api/safety/set-zone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x: Math.max(0, x - w / 2), y: Math.max(0, y - h / 2), w: w, h: h })
            }).then(() => {
                document.getElementById('zone-status').textContent = 'Area sudah diatur';
                document.getElementById('zone-status').className = 'status-safe';
                document.getElementById('zone-hint').textContent = 'Area terlarang aktif';
                this.showToast('Area terlarang berhasil diatur', 'success');
            });

            this.isDrawingZone = false;
            img.removeEventListener('click', handler);
        };

        img.addEventListener('click', handler);
    },

    async resetZone() {
        await fetch('/api/safety/reset-zone', { method: 'POST' });
        document.getElementById('zone-status').textContent = 'Belum diatur';
        document.getElementById('zone-status').className = '';
        document.getElementById('zone-hint').textContent = 'Klik pada kamera untuk menggambar area';
        this.showToast('Area terlarang direset', 'info');
    },

    async clearAreaLogs() {
        await fetch('/api/safety/logs/clear', { method: 'POST' });
        document.getElementById('area-log-body').innerHTML = '<tr><td colspan="5" class="empty-state">Belum ada riwayat</td></tr>';
        this.showToast('Riwayat Safety Area dihapus', 'info');
    },

    // ========== TELEGRAM ==========
    setupTelegramConfigs() {
        document.getElementById('btn-save-tg-apd').addEventListener('click', () => this.saveTGConfig('apd'));
        document.getElementById('btn-test-tg-apd').addEventListener('click', () => this.testTG('apd'));
        document.getElementById('btn-save-tg-area').addEventListener('click', () => this.saveTGConfig('safety-area'));
        document.getElementById('btn-test-tg-area').addEventListener('click', () => this.testTG('safety-area'));
    },

    async saveTGConfig(feature) {
        const prefix = feature === 'apd' ? 'apd' : 'area';
        const botToken = document.getElementById(`tg-bot-token-${prefix}`).value.trim();
        const chatId = document.getElementById(`tg-chat-id-${prefix}`).value.trim();

        await fetch('/api/telegram/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feature, bot_token: botToken, chat_id: chatId })
        });
        this.showToast('Konfigurasi Telegram disimpan', 'success');
    },

    async testTG(feature) {
        const prefix = feature === 'apd' ? 'apd' : 'area';
        const botToken = document.getElementById(`tg-bot-token-${prefix}`).value.trim();
        const chatId = document.getElementById(`tg-chat-id-${prefix}`).value.trim();

        if (!botToken || !chatId) {
            this.showToast('Isi Bot Token dan Chat ID', 'warning');
            return;
        }

        const res = await fetch('/api/telegram/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feature, bot_token: botToken, chat_id: chatId })
        });
        const data = await res.json();
        this.showToast(data.message, data.success ? 'success' : 'error');
    },

    async loadTelegramConfigs() {
        try {
            const res1 = await fetch('/api/telegram/config/apd');
            const cfgApd = await res1.json();
            document.getElementById('tg-bot-token-apd').value = cfgApd.bot_token || '';
            document.getElementById('tg-chat-id-apd').value = cfgApd.chat_id || '';

            const res2 = await fetch('/api/telegram/config/safety-area');
            const cfgArea = await res2.json();
            document.getElementById('tg-bot-token-area').value = cfgArea.bot_token || '';
            document.getElementById('tg-chat-id-area').value = cfgArea.chat_id || '';
        } catch (e) { }
    },

    // ========== DASHBOARD ==========
    async loadDashboard() {
        try {
            const res = await fetch('/api/dashboard');
            const d = await res.json();
            document.getElementById('stat-alarm').textContent = d.alarm_count;
            document.getElementById('stat-log').textContent = d.entry_count;

            const tbody = document.getElementById('dashboard-log-body');
            if (d.recent_logs && d.recent_logs.length > 0) {
                tbody.innerHTML = d.recent_logs.map(log => {
                    const cls = (log.status === 'Bahaya' || log.status === 'Tidak Lengkap') ? 'status-danger' : 'status-safe';
                    return `<tr>
                        <td>${log.waktu}</td>
                        <td>${log.fitur}</td>
                        <td class="${cls}">${log.status}</td>
                        <td>${log.keterangan || '-'}</td>
                    </tr>`;
                }).join('');
            }

            if (d.model_info) {
                const mi = d.model_info;
                const apdEl = document.getElementById('model-apd');
                if (apdEl) {
                    if (mi.ppe_model) {
                        apdEl.textContent = 'YOLOv8 Custom (Loaded)';
                        apdEl.style.color = '#28a745';
                    } else {
                        apdEl.textContent = 'YOLOv8 Custom (Not Found)';
                        apdEl.style.color = '#ffc107';
                    }
                }
            }
        } catch (e) { }
    },

    // ========== CAMERAS ==========
    async loadCameras() {
        try {
            const res = await fetch('/api/cameras');
            const data = await res.json();
            if (data.cameras && data.cameras.length > 0) {
                const currentApd = document.getElementById('apd-camera-select').value;
                const currentArea = document.getElementById('area-camera-select').value;

                const options = data.cameras.map(c => {
                    const inUseBy = c.used_by || [];
                    const disabledApd = inUseBy.includes('safety') ? ' disabled' : '';
                    const disabledArea = inUseBy.includes('apd') ? ' disabled' : '';
                    const tagApd = inUseBy.includes('safety') ? ' [Dipakai Safety]' : '';
                    const tagArea = inUseBy.includes('apd') ? ' [Dipakai APD]' : '';
                    return { id: c.id, name: c.name, resolution: c.resolution, disabledApd, disabledArea, tagApd, tagArea };
                });

                document.getElementById('apd-camera-select').innerHTML = options.map(c =>
                    `<option value="${c.id}"${c.disabledApd}>${c.name} (${c.resolution})${c.tagApd}</option>`
                ).join('');
                document.getElementById('area-camera-select').innerHTML = options.map(c =>
                    `<option value="${c.id}"${c.disabledArea}>${c.name} (${c.resolution})${c.tagArea}</option>`
                ).join('');

                if (currentApd) document.getElementById('apd-camera-select').value = currentApd;
                if (currentArea) document.getElementById('area-camera-select').value = currentArea;
            }
        } catch (e) { }
    },

    // ========== BUZZER ==========
    async testBuzzer(feature) {
        try {
            await fetch(`/api/${feature}/test-buzzer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'danger' })
            });
            this.showToast('Test buzzer - mendengarkan bunyi', 'info');
        } catch (e) {
            this.showToast('Gagal test buzzer', 'error');
        }
    },

    // ========== HELPERS ==========
    setLamp(prefix, color) {
        ['red', 'yellow', 'green'].forEach(c => {
            const lamp = document.getElementById(`${prefix}-lamp-${c}`);
            if (lamp) lamp.classList.toggle('active', c === color);
        });
    },

    showToast(message, type = 'info', duration = 4000) {
        const toast = document.getElementById('notification-toast');
        const icons = { success: '&#10004;', error: '&#10060;', warning: '&#9888;', info: '&#8505;' };
        toast.className = `notification-toast ${type}`;
        toast.querySelector('.toast-icon').innerHTML = icons[type] || icons.info;
        toast.querySelector('.toast-message').textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), duration);
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
