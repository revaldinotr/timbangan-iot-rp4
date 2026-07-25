# Arsitektur Workflow

Workflow terdiri dari **16 node** yang dikelompokkan menjadi lima tahap.

---

## Tahap 1 — Penerimaan & Penyaringan

### `WhatsApp Webhook`
`n8n-nodes-base.webhook` · POST

Titik masuk. Fonnte mengirim payload berisi `body.sender`, `body.message`,
`body.device`, `body.session`, `body.botNumber`.

> `path` dan `webhookId` sengaja dikosongkan di repo agar n8n meng-generate nilai baru
> saat import — endpoint Anda tidak bocor ke publik.

### `Bukan Echo Bot?`
`if` · dua kondisi digabung AND

1. `body.sender` tidak kosong
2. `body.sender` ≠ `body.device`

Menyaring event yang berasal dari device bot sendiri (echo balasan, update status).
Tanpa node ini, bot bisa membalas dirinya sendiri tanpa henti dan menghabiskan kuota
Fonnte.

Cabang **false** → `Abaikan Event` (NoOp, berhenti diam-diam).

### `Has Text?`
`if` · `body.message` tidak kosong

Fonnte **tidak** mengirim field `body.type`, jadi pengecekan hanya pada isi pesan.
Cabang false → `Balas Pesan Tidak Valid`.

---

## Tahap 2 — Autentikasi

### `Cek Status Sesi PIN`
`code` · inti keamanan workflow

State machine dengan empat kondisi keluaran:

| State | Pemicu | Aksi |
|---|---|---|
| `AUTHENTICATED` | Sesi valid & pesan bukan `LOGIN` | Teruskan ke pipeline data |
| `WAITING_PIN` | Pesan = `LOGIN` | Minta PIN |
| `LOGIN_SUCCESS` | PIN cocok saat menunggu PIN | Buat sesi, kirim sambutan |
| `WRONG_PIN` | PIN salah | Hapus sesi, minta ulangi |
| `NOT_LOGGED_IN` | Belum login, tidak ketik LOGIN | Minta login dulu |

**Penyimpanan sesi.** `$getWorkflowStaticData('global')`, dikunci per nomor pengirim
(sudah dibersihkan dari sufiks `@s.whatsapp.net` / `@c.us`).

```js
sessions[senderClean] = { waitingForPin: false, loginTime: Date.now() }
```

**Sliding session.** Jika `SLIDING_SESSION = true`, `loginTime` diperbarui tiap
aktivitas sehingga user aktif tidak terputus di tengah percakapan.

**Pruning.** Setiap eksekusi menghapus sesi yang: sudah lewat `SESSION_MINUTES`,
menunggu PIN lebih dari 10 menit, atau berbentuk tidak valid. Mencegah static data
membengkak tanpa batas.

**Sumber PIN.** `process.env.STOK_PIN`, dengan fallback `'0000'` yang hanya untuk demo.

> ⚠️ **Keterbatasan:** satu PIN berlaku untuk semua nomor. Tidak ada pemisahan hak akses
> maupun pembatasan percobaan. Lihat `SECURITY.md`.

### `Sudah Login?`
`if` · `state == "AUTHENTICATED"`

True → ambil data. False → `Balas Pesan Auth` (mengirim `replyMessage` yang sudah
disiapkan state machine).

---

## Tahap 3 — Pengambilan Data

### `Ambil Data Sheets`
`httpRequest` · Google Sheets API v4

Membaca seluruh Sheet1 dalam mode `FORMATTED_VALUE` (default) — nilai seperti yang
terlihat manusia.

### `Ambil Link Foto`
`httpRequest` · `?valueRenderOption=FORMULA`

**Kenapa dua kali baca?** Mode `FORMATTED_VALUE` mengembalikan sel **kosong** untuk
formula `IMAGE()` dan `HYPERLINK()`. Untuk mengekstrak file ID Google Drive, sheet harus
dibaca ulang dalam mode FORMULA.

Kedua node memakai `retryOnFail` (3× dengan jeda 2 detik),
`onError: continueRegularOutput`, dan `alwaysOutputData` — kegagalan Google API tidak
menghentikan workflow.

---

## Tahap 4 — Pengolahan

### `Format Data`
`code` · menggabungkan kedua hasil pembacaan

Keluaran:
- `sheetsContext` — tabel teks siap dikirim ke LLM
- `photoMap` — array `{ id, fileId, sayur, berat, waktu }`

**Deteksi kolom bersifat longgar** — dicocokkan secara *case-insensitive* dan sebagian:

| Dicari | Cocok dengan |
|---|---|
| `foto` | "Foto", "foto barang", "FOTO" |
| `sayur` | "Jenis Sayur", "sayuran" |
| `berat` atau `kg` | "Berat (Kg)", "berat" |
| `time` / `stamp` / `tanggal` | "Timestamps", "Tanggal" |

Ini membuat spreadsheet yang sedikit berbeda tetap bisa dipakai.

**Ekstraksi file ID** mencoba tiga pola berurutan:
1. `/d/([-\w]{20,})` — format HYPERLINK
2. `[?&]id=([-\w]{20,})` — format IMAGE
3. `([-\w]{25,})` — token panjang apa pun sebagai cadangan

**ID baris** dibuat dari indeks (baris ke-1 setelah header = ID 1). AI memakai ID ini
untuk menunjuk foto mana yang diminta.

### `AI Agent` + `Groq Chat Model` + `Window Buffer Memory`
`@n8n/n8n-nodes-langchain.agent`

- Model: `meta-llama/llama-4-scout-17b-16e-instruct`, temperature `0.5`
- Memori: 6 percakapan terakhir, dikunci per `body.sender`
- Seluruh isi spreadsheet disisipkan ke tiap prompt (bukan RAG — cocok untuk data
  berskala pasar, tidak untuk ribuan baris)

System prompt memuat tiga blok aturan: format WhatsApp, cara menyajikan data stok, dan
protokol pengiriman foto.

**Protokol foto.** Bila user minta foto, AI menambahkan penanda di baris paling akhir:

```
[[SEND_PHOTOS: 3,7,9]]
```

Penanda ini dihapus sebelum pesan dikirim ke user.

---

## Tahap 5 — Pengiriman

### `Sanitasi Output`
`code`

1. Cari dan ekstrak penanda `[[SEND_PHOTOS: ...]]` dengan regex
2. Hapus penanda dari teks balasan
3. Sediakan teks cadangan bila keluaran AI kosong
4. Potong pesan pada 3900 karakter (batas WhatsApp ±4096)

Keluaran bercabang ke dua jalur paralel: teks dan foto.

### `Ada Chat ID?` → `Kirim ke WhatsApp`
Memastikan `senderClean` tidak kosong sebelum memanggil API Fonnte.

### `Ada Foto Diminta?` → `Siapkan Item Foto` → `Kirim Foto ke WhatsApp`
`Siapkan Item Foto` menyusun **satu** pesan teks berisi daftar link Drive, dibatasi 25
foto.

> **Kenapa link, bukan gambar?** Paket gratis Fonnte tidak mendukung pengiriman media
> lewat URL. Untuk mengirim gambar sungguhan, dibutuhkan paket berbayar dan penggantian
> node ini dengan panggilan endpoint media Fonnte.

---

## Ringkasan Penanganan Error

| Mekanisme | Diterapkan pada | Efek |
|---|---|---|
| `retryOnFail` 3× jeda 2 dtk | semua node HTTP | Tahan gangguan jaringan sesaat |
| `onError: continueRegularOutput` | semua node HTTP | Kegagalan tidak menghentikan alur |
| `alwaysOutputData` | node Sheets | Node hilir tetap menerima input |
| `try/catch` | semua node Code | Data cacat tidak merusak eksekusi |
| Pemotongan pesan | `Sanitasi Output` | Cegah penolakan dari WhatsApp |
| Penyaring echo | `Bukan Echo Bot?` | Cegah loop tak berujung |

---

## Batas Skala yang Diketahui

| Aspek | Batas | Alasan |
|---|---|---|
| Baris spreadsheet | ±200–500 | Seluruh sheet masuk ke prompt LLM |
| Sesi bersamaan | Ratusan | Static data disimpan di memori |
| Pesan per menit | Tergantung paket Fonnte | Rate limit gateway |
| Panjang balasan | 3900 karakter | Batas WhatsApp |
| Foto per permintaan | 25 | Pengaman di `Siapkan Item Foto` |

Untuk data lebih besar, ganti pendekatan "seluruh sheet ke prompt" dengan vector store
atau query berbasis filter.
