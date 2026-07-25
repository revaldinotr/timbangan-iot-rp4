# Panduan Kontribusi

Terima kasih sudah tertarik berkontribusi! 🥬

## ⚠️ Aturan Nomor Satu: Sanitasi Sebelum Commit

Export workflow n8n **selalu** memuat data spesifik instance Anda:

- ID Google Spreadsheet asli
- Path & UUID webhook produksi
- ID credential internal n8n
- `instanceId` — sidik jari instance Anda
- PIN yang di-hardcode sebagai fallback

**Wajib** dibersihkan sebelum masuk Git:

```bash
python3 scripts/sanitize-workflow.py export-mentah.json workflows/manajemen-stok-sayur-wa-pin.n8n.json
python3 scripts/validate-workflow.py workflows/manajemen-stok-sayur-wa-pin.n8n.json
```

CI akan menolak PR yang masih mengandung rahasia. Namun **jangan mengandalkan CI** —
sekali rahasia masuk riwayat Git, menghapusnya butuh `git filter-repo` atau repo baru.

## Alur Kerja

1. **Fork** repositori ini
2. Buat branch: `git checkout -b fitur/nama-fitur`
3. Import workflow ke n8n Anda, lakukan perubahan
4. Export, **sanitasi**, dan **validasi**
5. Uji ujung-ke-ujung dengan nomor WhatsApp sungguhan
6. Commit dengan pesan yang jelas
7. Buka Pull Request

## Konvensi Commit

Mengikuti [Conventional Commits](https://www.conventionalcommits.org):

```
feat:     fitur baru
fix:      perbaikan bug
docs:     perubahan dokumentasi
refactor: perubahan struktur tanpa mengubah perilaku
perf:     peningkatan performa
chore:    tooling, CI, dependensi
security: perbaikan terkait keamanan
```

Contoh: `feat: tambahkan rate limit pada percobaan PIN`

## Panduan Gaya untuk Node Code

- Beri komentar header di tiap node Code yang menjelaskan tujuannya
- Tulis komentar dalam **Bahasa Indonesia** — audiens utama proyek ini
- Bungkus akses data eksternal dengan `try/catch`
- Jangan pernah hardcode rahasia; baca dari `process.env`
- Selalu kembalikan array `[{ json: {...} }]`

## Penamaan Node

Node diberi nama dalam Bahasa Indonesia dan **direferensikan langsung** dalam kode
(mis. `$('Format Data')`). Jika Anda mengganti nama node, **cari dan perbarui semua
referensinya** — bila terlewat, workflow akan rusak saat runtime.

## Menguji Perubahan

Belum ada test otomatis (kontribusi sangat diterima!). Minimal, uji manual:

- [ ] `LOGIN` → diminta PIN
- [ ] PIN benar → login berhasil
- [ ] PIN salah → ditolak, sesi dihapus
- [ ] Pertanyaan tanpa login → diminta login dulu
- [ ] Pertanyaan data setelah login → jawaban berisi data sheet
- [ ] Permintaan foto → terkirim link Drive
- [ ] Sheet kosong → pesan gagal yang ramah, bukan error
- [ ] Google Sheets down → workflow tidak berhenti total
- [ ] Sesi kedaluwarsa setelah durasi habis

## Pertanyaan?

Buka [Discussion](../../discussions) atau issue dengan label `question`.
