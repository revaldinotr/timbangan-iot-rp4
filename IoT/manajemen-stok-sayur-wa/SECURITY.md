# Kebijakan Keamanan

## Melaporkan Kerentanan

**Jangan membuka issue publik untuk laporan keamanan.**

Kirim laporan ke: `<email-keamanan-anda>`

Sertakan bila memungkinkan:
- Deskripsi kerentanan dan dampaknya
- Langkah reproduksi
- Versi n8n dan versi workflow yang terpengaruh

Kami berusaha membalas dalam **7 hari kerja**.

## Cakupan

Termasuk dalam cakupan:
- Bypass autentikasi PIN
- Kebocoran sesi antar nomor WhatsApp
- Injeksi lewat pesan WhatsApp yang mempengaruhi node Code
- Prompt injection yang membuat AI membocorkan data di luar hak akses
- Kebocoran kredensial melalui export workflow

Di luar cakupan:
- Kerentanan pada n8n, Fonnte, Groq, atau Google (laporkan ke vendor terkait)
- Serangan yang membutuhkan akses fisik ke server
- Social engineering terhadap pengguna

## Keterbatasan yang Sudah Diketahui

Berikut sudah diketahui dan **tidak perlu** dilaporkan — kontribusi perbaikan justru
sangat diterima:

| Keterbatasan | Dampak | Status |
|---|---|---|
| PIN tunggal untuk semua pengguna | Tidak ada pemisahan hak akses | Roadmap |
| Tidak ada rate limit pada percobaan PIN | PIN pendek rentan ditebak | Roadmap |
| Sesi disimpan di static data n8n | Hilang saat restart; tidak cocok multi-instance | Roadmap |
| Tidak ada audit log | Sulit melacak siapa mengakses apa | Roadmap |
| Nomor pengirim dipercaya apa adanya | Spoofing bergantung keamanan gateway | By design |

## Praktik Aman untuk Pengguna

1. Set `STOK_PIN` lewat environment variable, jangan hardcode.
2. Gunakan PIN minimal 6 digit dan ganti berkala.
3. Aktifkan HTTPS untuk endpoint webhook.
4. Aktifkan basic auth pada panel n8n.
5. Simpan `N8N_ENCRYPTION_KEY` di tempat aman — tanpa itu credential tidak bisa dipulihkan.
6. Batasi izin berbagi spreadsheet Google.
7. Selalu jalankan `scripts/sanitize-workflow.py` sebelum commit.
