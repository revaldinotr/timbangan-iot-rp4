# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [Unreleased]

### Rencana
- Buffer offline di perangkat saat jaringan putus
- Rate limiting percobaan PIN chatbot
- Kalibrasi multi-titik

## [1.0.0] - 2026-07-25

Rilis publik pertama, menyertai laporan Tugas Akhir.

### Ditambahkan — Perangkat
- Pembacaan berat load cell + HX711 dengan filter berlapis
  (trimmed mean → rolling median → deadband → stable lock)
- Auto-tare setelah idle 120 detik pada kondisi kosong
- Deteksi jenis sayuran YOLOv5 TFLite (kentang, tomat, wortel)
  dengan konfirmasi 8 frame
- Tampilan LCD I2C 16×2 realtime beserta splash screen
- Capture foto dan pengiriman gabungan lewat satu tombol GPIO
- Arsitektur tiga thread dengan state terlindungi lock
- Shutdown berurutan yang melepas kamera, LCD, dan GPIO dengan rapi
- `calibrate.py` — pencarian faktor kalibrasi terpandu
- Unit systemd untuk menjalankan otomatis saat boot

### Ditambahkan — Apps Script
- Endpoint `doPost` menerima berat, jenis, dan foto base64
- Penyimpanan foto ke Google Drive dengan berbagi lewat link
- Penulisan baris ke Sheets dengan formula `HYPERLINK` + `IMAGE`
- Endpoint `doGet` untuk pengujian cepat tanpa foto

### Ditambahkan — Chatbot
- Workflow n8n dengan autentikasi PIN (state machine 5 kondisi)
- Sesi 60 menit dengan sliding session dan pembersihan otomatis
- AI Agent berbasis Groq dengan memori 6 percakapan
- Pembacaan Sheets ganda (FORMATTED + FORMULA) untuk ekstraksi link foto
- Pengiriman link foto Drive lewat WhatsApp
- Penyaring echo bot dan retry otomatis pada seluruh node HTTP

### Ditambahkan — Infrastruktur & Dokumentasi
- Self-host n8n di Raspberry Pi lewat Cloudflare Tunnel
- Dokumentasi lengkap: setup, hardware, kalibrasi, arsitektur, troubleshooting
- CI: pemindaian rahasia, validasi Python, validasi workflow, ShellCheck

### Keamanan
- Seluruh kredensial dipindahkan dari kode ke `.env` dan Script Properties
- Token bersama opsional pada endpoint Apps Script dengan perbandingan
  waktu-tetap
- `scripts/check-secrets.sh` — pemindai rahasia untuk seluruh repositori
- `scripts/sanitize-workflow.py` — pembersih export n8n sebelum commit
- Port n8n di-bind ke localhost; akses publik hanya lewat tunnel

[Unreleased]: https://github.com/revaldinotr/timbangan-iot-rp4/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/revaldinotr/timbangan-iot-rp4/releases/tag/v1.0.0
