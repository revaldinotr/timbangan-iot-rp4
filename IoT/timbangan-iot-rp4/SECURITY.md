# Kebijakan Keamanan

## Melaporkan Kerentanan

**Jangan membuka issue publik untuk laporan keamanan.**

Kirim ke: `<email-keamanan-anda>`

Sertakan bila memungkinkan: deskripsi kerentanan, dampak, langkah reproduksi, dan
komponen yang terpengaruh. Kami berusaha membalas dalam **7 hari kerja**.

## Cakupan

**Termasuk**
- Bypass token bersama pada endpoint Apps Script
- Bypass autentikasi PIN chatbot
- Kebocoran sesi antar nomor WhatsApp
- Injeksi lewat pesan WhatsApp yang mempengaruhi node Code
- Prompt injection yang membocorkan data di luar hak akses
- Kebocoran kredensial lewat export workflow atau berkas repositori
- Eskalasi lokal pada perangkat lewat konfigurasi yang tidak aman

**Di luar cakupan**
- Kerentanan pada n8n, Fonnte, Groq, Google, atau Cloudflare — laporkan ke vendor
- Serangan yang membutuhkan akses fisik ke perangkat
- Social engineering terhadap pengguna

## Keterbatasan yang Sudah Diketahui

Berikut sudah diketahui dan **tidak perlu** dilaporkan — perbaikan justru sangat
diterima:

| Keterbatasan | Dampak | Status |
|---|---|---|
| Endpoint Apps Script harus "Anyone" | Endpoint tulis publik bila token tidak aktif | Dimitigasi token bersama |
| PIN tunggal untuk semua pengguna | Tidak ada pemisahan hak akses | Roadmap |
| Tidak ada rate limit percobaan PIN | PIN pendek rentan ditebak | Roadmap |
| Sesi di static data n8n | Hilang saat restart; tidak cocok multi-instance | Roadmap |
| Foto Drive dapat diakses lewat link | Diperlukan agar tampil di Sheets & WhatsApp | By design |
| Nomor pengirim dipercaya apa adanya | Spoofing bergantung keamanan gateway | By design |
| Tidak ada audit log | Sulit melacak akses | Roadmap |
| Data gagal kirim hilang | Belum ada buffer offline | Roadmap |

## Praktik Aman untuk Pengguna

1. Aktifkan `SHARED_TOKEN` di Apps Script — lihat
   [`docs/SECURITY-NOTES.md`](docs/SECURITY-NOTES.md)
2. Buat deployment baru bila Deployment ID pernah tersebar
3. Set `STOK_PIN` minimal 6 digit lewat environment variable
4. Aktifkan basic auth n8n dan gunakan HTTPS
5. Cadangkan `N8N_ENCRYPTION_KEY` di luar perangkat
6. Jangan port-forward port 5678; gunakan Cloudflare Tunnel
7. Batasi izin berbagi spreadsheet
8. Jalankan `bash scripts/check-secrets.sh` sebelum setiap commit
