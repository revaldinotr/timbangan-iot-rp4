# Pemecahan Masalah

## Bot tidak membalas sama sekali

**1. Cek workflow aktif.** Toggle **Active** di kanan atas harus menyala. Webhook test
hanya hidup 120 detik setelah klik "Listen".

**2. Cek URL webhook di Fonnte.** Harus **Production URL**, bukan Test URL. Salin ulang
dari node `WhatsApp Webhook`.

**3. Cek device Fonnte terhubung.** Panel Fonnte → status device harus `connected`.
Jika `disconnected`, pindai ulang QR.

**4. Lihat riwayat eksekusi.** n8n → **Executions**. Jika kosong, webhook tidak pernah
menerima apa pun — masalah ada di sisi Fonnte atau jaringan.

**5. Self-host: cek `WEBHOOK_URL`.** Bila salah, n8n menampilkan URL yang tidak bisa
dijangkau dari luar. Harus URL publik dan diakhiri garis miring.

---

## Bot membalas dirinya sendiri berulang-ulang

Node `Bukan Echo Bot?` tidak berfungsi. Pastikan Fonnte mengirim field `body.device`.
Bila payload Anda memakai nama field berbeda, sesuaikan kondisi node tersebut.

Segera **nonaktifkan workflow** untuk menghentikan konsumsi kuota.

---

## PIN selalu ditolak

**Cek 1 — env terbaca?** Tambahkan sementara di awal node `Cek Status Sesi PIN`:

```js
console.log('PIN dari env:', process.env.STOK_PIN);
```

Lihat log eksekusi. Jika `undefined`, env tidak terbaca.

**Cek 2 — akses env diblokir?** Self-host butuh:

```
N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

**Cek 3 — spasi tersembunyi.** Kode memakai `.trim()` pada pesan, tapi nilai env bisa
punya spasi. Periksa `.env` Anda.

**Cek 4 — alurnya benar?** Harus `LOGIN` dulu, baru PIN. Mengirim PIN langsung tanpa
`LOGIN` akan masuk ke state `NOT_LOGGED_IN`.

---

## Sesi hilang terus / harus login berulang

Sesi disimpan di **static data** n8n yang tersimpan di memori proses. Restart n8n =
semua sesi hilang. Ini perilaku yang diketahui.

Selain itu, static data tidak dibagi antar instance — bila menjalankan n8n dalam mode
queue/multi-worker, sesi bisa tidak konsisten. Solusi jangka panjang: pindahkan sesi ke
Redis (ada di roadmap).

---

## "DATA TIDAK TERSEDIA"

**1. Sheet ID salah.** Pastikan `YOUR_GOOGLE_SHEET_ID` sudah diganti di **kedua** node:
`Ambil Data Sheets` dan `Ambil Link Foto`.

**2. Nama sheet salah.** URL menunjuk `/values/Sheet1`. Jika tab Anda bernama lain
(mis. `Stok`), sesuaikan URL-nya. Nama dengan spasi perlu di-encode: `Data%20Stok`.

**3. Credential kedaluwarsa.** Google OAuth bisa dicabut. Buka credential di n8n dan
klik **Reconnect**.

**4. Sheets API belum aktif.** Di Google Cloud Console, aktifkan **Google Sheets API**
untuk project Anda.

**5. Sheet benar-benar kosong.** Minimal harus ada baris header.

---

## Foto tidak terkirim

**1. Kolom foto kosong di mode FORMATTED.** Ini normal — itulah alasan ada node
`Ambil Link Foto` yang membaca mode FORMULA. Pastikan node ini tidak terhapus dan
terhubung setelah `Ambil Data Sheets`.

**2. AI tidak menulis penanda.** Lihat keluaran node `AI Agent`. Harus ada
`[[SEND_PHOTOS: 3,5]]` di baris terakhir. Bila tidak muncul, permintaan user mungkin
kurang eksplisit — coba "kirim foto tomat".

**3. Link Drive tidak bisa dibuka penerima.** Setel izin berbagi folder foto ke
"Anyone with the link — Viewer".

**4. Mengharapkan gambar, bukan link.** Paket gratis Fonnte tidak mendukung media. Ini
sesuai desain.

---

## Balasan berantakan di WhatsApp

Bila muncul tabel dengan `|` atau tebal `**seperti ini**`, AI mengabaikan system prompt.

- Pastikan system prompt di node `AI Agent` masih utuh
- Turunkan `temperature` (coba `0.3`)
- Model yang lebih kecil kadang kurang patuh pada instruksi format

---

## Balasan terpotong

Batas 3900 karakter di `Sanitasi Output` memang disengaja. Bila sering terpotong,
data Anda kemungkinan terlalu banyak — minta AI meringkas, atau pisahkan sheet arsip.

---

## Error 429 / rate limit

**Dari Groq:** kuota gratis habis. Tunggu reset atau upgrade.
**Dari Fonnte:** melebihi batas pesan paket Anda.

Kedua node HTTP sudah retry 3×, tapi retry tidak menolong bila kuota memang habis.

---

## Error 401 / 403

Credential bermasalah:

| Layanan | Penyebab umum |
|---|---|
| Fonnte | Token salah, atau header bukan `Authorization` |
| Google | OAuth kedaluwarsa/dicabut, atau API belum aktif |
| Groq | API key salah atau sudah dihapus |

---

## Masih bermasalah?

Buka [issue](../../issues) dengan menyertakan:

- Langkah reproduksi
- Screenshot riwayat eksekusi n8n (**sensor token & nomor telepon**)
- Versi n8n
- Cloud atau self-host

⚠️ **Jangan tempel token, API key, atau nomor WhatsApp** ke dalam issue publik.
