# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/),
dan proyek ini menggunakan [Semantic Versioning](https://semver.org/lang/id/).

## [Unreleased]

### Rencana
- PIN per-nomor (multi-user)
- Rate limiting percobaan PIN
- Input data lewat WhatsApp

## [1.0.0] - 2026-07-25

### Ditambahkan
- Workflow n8n awal untuk manajemen stok sayur via WhatsApp
- Autentikasi PIN dengan state machine 4 kondisi
- Sesi berbatas waktu (60 menit) dengan sliding session
- Pembersihan otomatis sesi kedaluwarsa
- Integrasi Google Sheets (mode FORMATTED_VALUE + FORMULA)
- Ekstraksi link foto Google Drive dari formula HYPERLINK/IMAGE
- AI Agent berbasis Groq dengan memori 6 percakapan
- Format balasan yang ramah tampilan WhatsApp
- Penyaring echo bot untuk mencegah loop balasan
- Retry otomatis (3×) pada semua panggilan HTTP
- Pemotongan pesan pada 3900 karakter

### Keamanan
- PIN dibaca dari environment variable `STOK_PIN`
- Script sanitasi untuk membersihkan export sebelum commit
- CI memindai rahasia yang tertinggal

[Unreleased]: https://github.com/<username>/manajemen-stok-sayur-wa/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/<username>/manajemen-stok-sayur-wa/releases/tag/v1.0.0
