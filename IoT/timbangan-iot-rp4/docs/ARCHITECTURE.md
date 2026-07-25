# Arsitektur Sistem

Dokumen ini menjelaskan cara kerja setiap bagian sistem, dari sensor hingga balasan
WhatsApp.

---

# Bagian A — Perangkat (`device/main.py`)

Program berjalan dengan **tiga thread** yang berdiri sendiri dan berkomunikasi lewat
satu kamus state yang dilindungi `threading.Lock`.

```
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  thread_berat  │  │  thread_jenis  │  │thread_lcd_refresh│
│                │  │                │  │                │
│  HX711 ──▶     │  │  Webcam ──▶    │  │  antrian ──▶   │
│  filter ──▶    │  │  YOLOv5 ──▶    │  │  LCD I2C       │
│  state         │  │  state         │  │                │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        └───────────────────┴───────────────────┘
                            │
                   _state (dilindungi _lock)
                            │
                    ┌───────┴────────┐
                    │ _btn_callback  │  interrupt GPIO22
                    │  kirim_semua() │
                    └────────────────┘
```

Pemisahan ini penting: inferensi TFLite memakan ratusan milidetik, dan tanpa thread
terpisah pembacaan berat akan tersendat setiap kali model berjalan.

## A.1 Jalur Pembacaan Berat

`thread_berat` menjalankan siklus berikut setiap `INTERVAL_BERAT` (0,05 detik):

**1. Ambil sampel mentah** — `_hx711_read_raw_samples()` membaca 5 sampel dari HX711.

**2. Buang nilai ekstrem** — `_trim_core()` mengurutkan sampel lalu membuang 20 %
teratas dan terbawah, menyisakan 3 nilai tengah. Ini meredam spike akibat EMI dan
sentuhan pada konektor — penyebab derau paling umum pada HX711.

**3. Konversi ke gram**

```python
grams = [(r - tare_val) / CALIBRATION_FACTOR for r in core]
```

**4. Median dan sebaran** — median dipakai sebagai nilai, sebaran (`max − min`)
dipakai sebagai indikator kestabilan.

**5. `WeightFilter.update()`** — rangkaian tahap penyaringan:

| Tahap | Fungsi |
|---|---|
| Gerbang kestabilan | Menolak pembacaan bila sebaran terlalu besar (opsional) |
| Deadband nol | Nilai di bawah `DEADBAND_KG` (0,05 kg) dianggap nol |
| Rolling median | Median bergerak 3 sampel |
| Konfirmasi lompatan | Perubahan besar harus muncul beberapa kali (dinonaktifkan) |
| **Stable lock** | Inti pengalaman pengguna — lihat di bawah |

### Stable Lock

Meniru perilaku timbangan digital komersial. Setelah pembacaan berada dalam
toleransi ±200 g selama 4 siklus berturut-turut (±2 detik), nilai **dikunci** dan
layar berhenti berkedip.

Kunci dilepas bila salah satu terjadi:

- Berat berubah ≥ 1 kg (`LOCK_RELEASE_DELTA_KG`) — barang diganti
- Berat turun di bawah 0,15 kg (`LOCK_RELEASE_ZERO_KG`) — barang diangkat

Tanpa mekanisme ini, digit terakhir akan terus bergoyang dan pedagang kesulitan
membaca angkanya.

### Auto-tare

Bila timbangan kosong (di bawah `AUTOTARE_ZERO_KG`) selama `AUTOTARE_IDLE_SEC`
(120 detik), sistem melakukan tare ulang otomatis. Ini mengoreksi drift termal dan
sisa beban yang menempel tanpa perlu campur tangan pengguna.

## A.2 Jalur Deteksi Jenis

`thread_jenis` menjalankan pipeline berikut:

**1. Baca frame** — webcam pada 1280×720. Resolusi capture sengaja **dipisah** dari
ukuran input model: piksel yang lebih banyak sebelum resize membuat objek kecil atau
jauh lebih mungkin terdeteksi.

**2. Preprocess** — letterbox ke 640×640 dengan menjaga rasio aspek, lalu normalisasi.

**3. Inferensi** — interpreter TFLite dengan 4 thread (CM4 memiliki 4 core Cortex-A72).

**4. Postprocess** — konversi format `xywh` ke `xyxy`, filter berdasarkan
`CONF_THRESH` (0,08), lalu Non-Maximum Suppression dengan `IOU_THRESH` (0,15).

**5. Konfirmasi temporal** — `_jenis_terkonfirmasi()` menampung riwayat deteksi dalam
`deque` dan hanya menyatakan jenis sah setelah konsisten pada `CONFIRM_FRAMES`
(8 frame). Ini mencegah label berkedip-ganti saat kondisi cahaya berubah.

> Ambang confidence 0,08 tergolong sangat rendah. Nilai ini dipilih agar deteksi tetap
> terjadi pada kondisi cahaya pasar yang tidak ideal, dengan konsekuensi lebih banyak
> deteksi palsu — yang kemudian disaring oleh konfirmasi 8 frame di atas.

## A.3 Jalur Tampilan

`thread_lcd_refresh` adalah **satu-satunya** yang menulis ke LCD, menerima perintah
lewat `queue.Queue`. Alasannya: LCD I2C tidak aman diakses dari banyak thread, dan
penulisan bersamaan akan menghasilkan karakter acak.

Saat booting, `_run_splash()` menampilkan tiga layar identitas selama 2 detik masing-
masing, sementara model dimuat dan tare awal dijalankan — waktu tunggu terpakai
sebagai umpan balik, bukan layar kosong.

## A.4 Jalur Pengiriman

Tombol GPIO22 memicu interrupt `_btn_callback` pada tepi turun:

**1. Debounce** — 300 ms secara perangkat lunak.

**2. Kunci anti-ganda** — `_kirim_lock.acquire(blocking=False)`. Bila pengiriman
sebelumnya masih berjalan, tekanan tombol diabaikan alih-alih menumpuk antrean.

**3. Capture** — `capture_on_button()` menyimpan frame beserta bounding box ke
`captures/`, kualitas JPEG 70.

**4. Kirim** — `kirim_semua()` menyusun payload 5 kunci (plus token bila diaktifkan)
dan mengirimkannya dalam **satu** POST.

Apps Script membalas dengan redirect 302; kode mengikutinya secara manual dengan GET
karena `allow_redirects=False` — perilaku khas web app Apps Script yang perlu
ditangani eksplisit.

**5. Umpan balik** — hasil ditampilkan di LCD lewat antrean, bukan ditulis langsung
dari konteks interrupt.

## A.5 Penanganan Error di Perangkat

| Mekanisme | Perilaku |
|---|---|
| Timeout 45 detik | Foto base64 bisa berukuran besar pada koneksi lambat |
| `ConnectionError` ditangkap | Pesan "cek WiFi/LAN" di LCD, program tetap jalan |
| Sampel HX711 gagal | Siklus dilewati, tidak menghentikan thread |
| Shutdown berurutan | Sinyal stop → LCD → kamera → HX711 → GPIO cleanup |

> **Keterbatasan yang diketahui:** data yang gagal terkirim **hilang** — belum ada
> buffer offline. Ini prioritas utama pada roadmap.

---

# Bagian B — Apps Script (`apps-script/pb_to_sheets.gs`)

`doPost()` menjalankan urutan berikut:

1. Parse JSON payload
2. Verifikasi `SHARED_TOKEN` bila diaktifkan → tolak bila tidak cocok
3. Decode base64 → buat blob JPEG
4. Simpan ke folder Drive (dibuat otomatis bila belum ada)
5. Set berbagi berkas ke `ANYONE_WITH_LINK / VIEW`
6. Buat header sheet bila baris masih kosong
7. Sisipkan baris: timestamp, berat, jenis, formula foto

Formula kolom foto menggabungkan dua fungsi:

```
=HYPERLINK("https://drive.google.com/file/d/ID/view";
           IMAGE("https://drive.google.com/uc?export=download&id=ID";4;60;80))
```

Perhatikan dua hal: pemisah argumen memakai **titik koma** (locale Indonesia), dan
kedua fungsi memakai **URL berbeda** — `/view` untuk halaman Drive, `uc?export` untuk
berkas mentah. URL `/view` tidak akan dirender sebagai gambar.

---

# Bagian C — Workflow n8n

Workflow terdiri dari **16 node** dalam lima tahap.

## C.1 Penerimaan & Penyaringan

**`WhatsApp Webhook`** — titik masuk POST dari Fonnte. Payload berisi `body.sender`,
`body.message`, `body.device`, `body.session`.

**`Bukan Echo Bot?`** — dua kondisi AND: `sender` tidak kosong, dan `sender ≠ device`.
Menyaring event dari device bot sendiri. Tanpa node ini bot akan membalas dirinya
sendiri tanpa henti dan menghabiskan kuota Fonnte.

**`Has Text?`** — Fonnte tidak mengirim field `body.type`, jadi pengecekan hanya pada
isi pesan.

## C.2 Autentikasi

**`Cek Status Sesi PIN`** — state machine dengan lima keluaran:

| State | Pemicu | Aksi |
|---|---|---|
| `AUTHENTICATED` | Sesi valid, pesan bukan LOGIN | Teruskan ke pipeline data |
| `WAITING_PIN` | Pesan = `LOGIN` | Minta PIN |
| `LOGIN_SUCCESS` | PIN cocok | Buat sesi, kirim sambutan |
| `WRONG_PIN` | PIN salah | Hapus sesi |
| `NOT_LOGGED_IN` | Belum login | Minta login dulu |

Sesi disimpan di `$getWorkflowStaticData('global')`, dikunci per nomor pengirim yang
sudah dibersihkan dari sufiks `@s.whatsapp.net`.

*Sliding session* memperbarui `loginTime` tiap aktivitas. *Pruning* menghapus sesi
kedaluwarsa dan sesi yang menunggu PIN lebih dari 10 menit, mencegah static data
membengkak.

## C.3 Pengambilan Data

**`Ambil Data Sheets`** — mode `FORMATTED_VALUE`, nilai seperti terlihat manusia.

**`Ambil Link Foto`** — mode `FORMULA`.

**Mengapa dibaca dua kali?** Mode `FORMATTED_VALUE` mengembalikan sel **kosong**
untuk formula `IMAGE()` dan `HYPERLINK()`. File ID Drive hanya bisa diekstrak dari
mode FORMULA. Inilah alasan kedua node ini harus tetap berpasangan.

## C.4 Pengolahan

**`Format Data`** — menggabungkan kedua hasil pembacaan menjadi `sheetsContext`
(tabel teks untuk LLM) dan `photoMap` (array `{id, fileId, sayur, berat, waktu}`).

Deteksi kolom bersifat longgar — dicocokkan *case-insensitive* dan sebagian, sehingga
spreadsheet yang sedikit berbeda tetap terbaca. Ekstraksi file ID mencoba tiga pola
berurutan: `/d/ID`, `?id=ID`, lalu token panjang apa pun.

**`AI Agent` + `Groq Chat Model` + `Window Buffer Memory`** — model
`llama-4-scout-17b-16e-instruct`, temperature 0,5, memori 6 percakapan terakhir.
Seluruh isi spreadsheet disisipkan ke tiap prompt — bukan RAG, sehingga cocok untuk
skala pasar tetapi tidak untuk ribuan baris.

Bila user meminta foto, AI menambahkan penanda di baris terakhir:

```
[[SEND_PHOTOS: 3,7,9]]
```

## C.5 Pengiriman

**`Sanitasi Output`** — ekstrak dan hapus penanda foto, sediakan teks cadangan bila
keluaran kosong, potong pada 3900 karakter (batas WhatsApp ±4096).

Bercabang ke dua jalur paralel: teks (`Ada Chat ID?` → `Kirim ke WhatsApp`) dan foto
(`Ada Foto Diminta?` → `Siapkan Item Foto` → `Kirim Foto ke WhatsApp`).

> **Kenapa link, bukan gambar?** Paket gratis Fonnte tidak mendukung pengiriman media
> lewat URL. Untuk mengirim gambar sungguhan diperlukan paket berbayar dan penggantian
> node terakhir dengan panggilan endpoint media Fonnte.

---

# Bagian D — Batas Skala yang Diketahui

| Aspek | Batas | Alasan |
|---|---|---|
| Baris spreadsheet | ±200–500 | Seluruh sheet masuk ke prompt LLM |
| Sesi chatbot bersamaan | Ratusan | Static data disimpan di memori |
| Panjang balasan | 3900 karakter | Batas WhatsApp |
| Foto per permintaan | 25 | Pengaman di `Siapkan Item Foto` |
| Kelas sayuran | 3 | Ditentukan saat pelatihan model |
| Kapasitas timbangan | 180 kg | Kapasitas load cell |
| Pesan per menit | Tergantung paket Fonnte | Rate limit gateway |
| Panggilan Apps Script | 20.000/hari | Kuota akun Google gratis |

Untuk data lebih besar, ganti pendekatan "seluruh sheet ke prompt" dengan vector
store atau query berbasis filter.
