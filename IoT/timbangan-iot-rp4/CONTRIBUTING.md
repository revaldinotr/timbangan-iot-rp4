# Panduan Kontribusi

Terima kasih sudah tertarik berkontribusi! 🥬⚖️

Proyek ini berawal dari Tugas Akhir Diploma III, dan dibuka agar bisa dikembangkan
lebih jauh oleh siapa saja — terutama untuk kebutuhan pedagang pasar tradisional.

---

## ⚠️ Aturan Nomor Satu: Jangan Commit Rahasia

Jalankan sebelum setiap commit:

```bash
bash scripts/check-secrets.sh
```

Yang **tidak boleh** masuk Git:

| Rahasia | Tempat yang benar |
|---|---|
| Deployment ID Apps Script | `device/.env` |
| Token bersama | `device/.env` + Script Properties |
| PIN chatbot | environment variable n8n |
| Token Fonnte / API key Groq | credential n8n |
| Token Cloudflare Tunnel | `infra/raspberry-pi/.env` |
| ID spreadsheet asli | placeholder di repo |

Bila mengubah workflow n8n, **wajib** disanitasi:

```bash
python3 scripts/sanitize-workflow.py export-mentah.json n8n/workflows/keluaran.json
python3 scripts/validate-workflow.py n8n/workflows/keluaran.json
```

CI akan menolak PR yang masih mengandung rahasia — tapi jangan mengandalkan CI.
Sekali rahasia masuk riwayat Git, menghapusnya butuh `git filter-repo` atau repo baru,
dan kredensialnya tetap harus dirotasi.

---

## Alur Kerja

1. **Fork** repositori
2. Buat branch: `git checkout -b fitur/nama-fitur`
3. Lakukan perubahan
4. Uji pada perangkat sungguhan bila menyentuh `device/`
5. `bash scripts/check-secrets.sh`
6. Commit dengan pesan jelas
7. Buka Pull Request

## Konvensi Commit

Mengikuti [Conventional Commits](https://www.conventionalcommits.org), dengan scope
sesuai komponen:

```
feat(device):   fitur baru di program Raspberry Pi
fix(n8n):       perbaikan bug workflow
docs(setup):    perubahan dokumentasi
refactor(gas):  restrukturisasi Apps Script
perf(device):   peningkatan performa
security:       perbaikan keamanan
chore:          tooling, CI, dependensi
```

Contoh: `feat(device): tambahkan buffer offline saat jaringan putus`

---

## Panduan per Komponen

### `device/` — Python

- Komentar dan pesan log dalam **Bahasa Indonesia** (audiens utama proyek ini)
- Jangan pernah hardcode rahasia; baca dari `os.getenv()`
- Nilai yang berbeda antar perangkat harus bisa diatur lewat `.env`
- Bungkus akses perangkat keras dengan `try/except` — jangan sampai satu sensor
  bermasalah menjatuhkan seluruh program
- Hormati batas thread: **hanya** `thread_lcd_refresh` yang boleh menulis ke LCD
- Jangan `sleep()` atau menulis LCD di dalam callback interrupt GPIO

### `apps-script/` — Google Apps Script

- Selalu kembalikan JSON dengan field `status`
- Verifikasi token sebelum efek samping apa pun
- Ingat kuota Google (6 menit per eksekusi, 90 menit per hari)

### `n8n/` — Workflow

- Nama node ditulis dalam Bahasa Indonesia dan **direferensikan langsung** di kode
  (mis. `$('Format Data')`). Bila mengganti nama node, cari dan perbarui **semua**
  referensinya — bila terlewat, workflow rusak saat runtime. `validate-workflow.py`
  memeriksa hal ini.
- Node HTTP sebaiknya memakai `retryOnFail` dan `onError: continueRegularOutput`

### `docs/` — Dokumentasi

- Bahasa Indonesia
- Sertakan perintah yang benar-benar bisa disalin-tempel
- Bila menambah langkah yang bisa gagal, tambahkan juga entri di
  `TROUBLESHOOTING.md`

---

## Menguji Perubahan

Belum ada test otomatis untuk perangkat keras (kontribusi sangat diterima!).
Uji manual minimum:

**Perangkat**
- [ ] Berat akurat pada beberapa beban acuan
- [ ] Stable lock mengunci dan melepas dengan wajar
- [ ] Auto-tare bekerja setelah idle
- [ ] Deteksi jenis benar untuk ketiga kelas
- [ ] Tombol mengirim tepat satu baris (tidak ganda)
- [ ] Data + foto masuk ke Sheets
- [ ] CTRL+C keluar bersih tanpa GPIO warning

**Chatbot**
- [ ] `LOGIN` → diminta PIN
- [ ] PIN benar → berhasil; PIN salah → ditolak
- [ ] Pertanyaan data terjawab benar
- [ ] Permintaan foto terkirim
- [ ] Sheet kosong → pesan ramah, bukan error

---

## Ide Kontribusi yang Dicari

**Prioritas tinggi**
- Buffer offline di perangkat (data gagal kirim saat ini **hilang**)
- Rate limiting percobaan PIN chatbot
- Kalibrasi multi-titik

**Menengah**
- Menambah kelas sayuran pada model
- Sesi n8n berbasis Redis
- Watchdog kamera
- Dukungan gateway WhatsApp alternatif

**Selalu diterima**
- Perbaikan dokumentasi
- Terjemahan
- Foto perakitan dan diagram wiring
- Laporan replikasi dari perangkat keras berbeda

---

## Pertanyaan?

Buka [Discussion](../../discussions) atau issue berlabel `question`.
Proyek ini banyak dipakai orang yang baru belajar elektronika — **tidak ada
pertanyaan yang bodoh.**
