# 🥬⚖️ Timbangan IoT — Sistem Akuisisi Data Berat Sayuran

Sistem akuisisi data berat sayuran pasar tradisional berbasis **Raspberry Pi Compute
Module 4**. Timbangan mengukur berat dengan **load cell + HX711**, mengenali jenis
sayuran lewat model **YOLOv5 TFLite**, memotret barangnya, lalu mengirim semuanya ke
**Google Sheets** dalam sekali tekan tombol.

Pedagang kemudian bisa menanyakan data stok kapan saja lewat **chatbot WhatsApp**
berbasis workflow **n8n** — tanpa membuka laptop, tanpa aplikasi tambahan.

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-CM4-C51A4A)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB)
![n8n](https://img.shields.io/badge/n8n-workflow-EA4B71)
![License](https://img.shields.io/badge/license-MIT-green)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

> **Tugas Akhir** — Diploma III Teknik Elektronika, Jurusan Teknik Elektro,
> Politeknik Negeri Sriwijaya, 2026.
> Oleh **Reval Dino Try Rahmady** (062330320631).

---

## 📑 Daftar Isi

- [Gambaran Sistem](#-gambaran-sistem)
- [Fitur](#-fitur)
- [Struktur Repositori](#-struktur-repositori)
- [Kebutuhan Perangkat Keras](#-kebutuhan-perangkat-keras)
- [Instalasi Cepat](#-instalasi-cepat)
- [Cara Kerja](#-cara-kerja)
- [Hasil Pengujian](#-hasil-pengujian)
- [Keamanan](#-keamanan)
- [Roadmap](#-roadmap)
- [Kontribusi](#-kontribusi)
- [Sitasi](#-sitasi)
- [Lisensi](#-lisensi)

---

## 🔭 Gambaran Sistem

Sistem terdiri dari **empat komponen** yang berjalan terpisah namun saling terhubung:

```
┌──────────────────────────────────────────────────────────────────┐
│  1. PERANGKAT  (device/)                                         │
│     Raspberry Pi CM4                                             │
│                                                                  │
│     Load cell 180kg ──▶ HX711 ──▶ ┐                             │
│     USB Webcam ──▶ YOLOv5 TFLite ─┼──▶ main.py ──▶ LCD 16x2     │
│     Push button GPIO22 ───────────┘        │                    │
└────────────────────────────────────────────┼────────────────────┘
                                             │ HTTPS POST
                                             │ {berat, jenis, foto b64}
                                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. APPS SCRIPT  (apps-script/)                                  │
│     doPost() ──▶ simpan foto ke Drive                            │
│               └─▶ tulis baris ke Google Sheets                   │
└────────────────────────────────────────────┬────────────────────┘
                                             │
                                             ▼
                              ┌──────────────────────────┐
                              │   Google Sheets          │
                              │   Timestamps │ Berat │   │
                              │   Jenis      │ Foto  │   │
                              └──────────┬───────────────┘
                                         │ dibaca
                                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. WORKFLOW n8n  (n8n/)                                         │
│     Webhook ──▶ Auth PIN ──▶ Baca Sheets ──▶ AI Agent (Groq)     │
│                                                   │              │
│                                                   ▼              │
│  4. INFRA  (infra/)                        Fonnte ──▶ WhatsApp   │
│     n8n self-host di Raspberry Pi                                │
│     + Cloudflare Tunnel (HTTPS publik)                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## ✨ Fitur

### Perangkat (`device/`)

| Fitur | Keterangan |
|---|---|
| ⚖️ **Pembacaan berat stabil** | Trimmed mean → rolling median → deadband → *stable lock*, meniru perilaku timbangan komersial |
| 🔄 **Auto-tare** | Nol ulang otomatis setelah idle 120 detik pada kondisi kosong |
| 🥕 **Deteksi jenis sayur** | YOLOv5 TFLite, 3 kelas (kentang, tomat, wortel), konfirmasi 8 frame |
| 📷 **Capture otomatis** | Foto diambil saat tombol ditekan, lengkap dengan bounding box |
| 🖥️ **LCD I2C 16×2** | Tampilan berat + jenis realtime, dengan splash screen saat booting |
| 🧵 **Arsitektur multi-thread** | Thread terpisah untuk berat, kamera, dan LCD — tidak saling memblokir |
| 🛡️ **Anti-noise** | Filter trimmed mean meredam spike dari EMI dan sentuhan konektor |
| 🔌 **Shutdown rapi** | CTRL+C melepas kamera, LCD, dan GPIO secara berurutan |

### Chatbot WhatsApp (`n8n/`)

| Fitur | Keterangan |
|---|---|
| 🔐 **Login PIN** | Ketik `LOGIN`, masukkan PIN. Sesi 60 menit dengan *sliding session* |
| 🤖 **Jawaban natural** | Ditenagai Groq — tanya bebas: "stok tomat berapa?" |
| 📷 **Kirim link foto** | Bot mengirim link Drive foto barang terkait |
| 📱 **Format ramah HP** | Tanpa tabel/markdown yang berantakan di WhatsApp |
| 🔁 **Anti echo-loop** | Event dari device sendiri disaring otomatis |

---

## 📁 Struktur Repositori

```
timbangan-iot-rp4/
├── README.md                      ← Anda di sini
├── LICENSE · CITATION.cff · CHANGELOG.md
├── CONTRIBUTING.md · SECURITY.md · CODE_OF_CONDUCT.md
├── .gitignore
│
├── device/                        ← 1. Program Raspberry Pi CM4
│   ├── main.py                    ← program utama (multi-thread)
│   ├── calibrate.py               ← cari CALIBRATION_FACTOR perangkat Anda
│   ├── requirements.txt
│   ├── .env.example               ← salin jadi .env, isi rahasia di sini
│   ├── model/README.md            ← cara menyiapkan best-fp32.tflite
│   └── systemd/timbangan.service  ← jalankan otomatis saat boot
│
├── apps-script/                   ← 2. Jembatan ke Sheets & Drive
│   ├── pb_to_sheets.gs
│   ├── appsscript.json
│   └── README.md
│
├── n8n/                           ← 3. Chatbot WhatsApp
│   ├── workflows/manajemen-stok-sayur-wa-pin.n8n.json
│   ├── docker-compose.yml
│   └── README.md
│
├── infra/raspberry-pi/            ← 4. Self-host n8n + Cloudflare Tunnel
│   ├── README.md
│   └── docker-compose.yml
│
├── docs/
│   ├── SETUP.md                   ← panduan lengkap ujung-ke-ujung
│   ├── HARDWARE.md                ← BOM, pinout, wiring
│   ├── CALIBRATION.md             ← teori & prosedur kalibrasi
│   ├── ARCHITECTURE.md            ← penjelasan setiap modul
│   ├── SPREADSHEET.md
│   ├── SECURITY-NOTES.md          ← ⚠️ WAJIB DIBACA
│   └── TROUBLESHOOTING.md
│
├── scripts/
│   ├── sanitize-workflow.py       ← bersihkan export n8n sebelum commit
│   ├── validate-workflow.py
│   └── check-secrets.sh
│
└── .github/                       ← CI: validasi + pemindaian rahasia
```

---

## 🔩 Kebutuhan Perangkat Keras

| Komponen | Spesifikasi |
|---|---|
| **Mikroprosesor** | Raspberry Pi Compute Module 4, 64-bit, 2 GB LPDDR4 |
| **Sensor berat** | Load cell 180 kg, output 1,0–2,0 mV/V, strain gauge (Wheatstone full bridge) |
| **Modul ADC** | HX711, 24-bit |
| **Sensor jenis** | USB webcam (disarankan 1280×720) |
| **Display** | LCD 16×2 antarmuka I2C, 5 V |
| **Input** | Push button (aktif rendah, pull-up internal) |
| **Power supply** | Input 110–220 VAC → Output 5 VDC 3 A |
| **Konektivitas** | WiFi / LAN / modem |

Detail wiring dan pinout: [`docs/HARDWARE.md`](docs/HARDWARE.md)

---

## 🚀 Instalasi Cepat

Sistem punya empat bagian. Pasang berurutan — tiap bagian bisa diuji sendiri.

### 1️⃣ Google Sheets + Apps Script

```bash
# Buat spreadsheet baru, lalu Extensions → Apps Script
# Tempel isi apps-script/pb_to_sheets.gs
# Deploy → New deployment → Web app → Execute as: Me, Access: Anyone
```

Salin **Deployment ID** dari URL. Aktifkan token bersama di
**Project Settings → Script Properties** (`SHARED_TOKEN`).

Detail: [`apps-script/README.md`](apps-script/README.md)

### 2️⃣ Perangkat Raspberry Pi

```bash
git clone https://github.com/revaldinotr/timbangan-iot-rp4.git
cd timbangan-iot-rp4/device

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env                    # isi GAS_SCRIPT_ID dan GAS_SHARED_TOKEN
```

Letakkan model di `device/model/best-fp32.tflite`
(lihat [`device/model/README.md`](device/model/README.md)).

**Kalibrasi wajib** — faktor bawaan tidak akan cocok untuk perangkat Anda:

```bash
python3 calibrate.py         # ikuti instruksi, salin hasilnya ke .env
```

Jalankan:

```bash
python3 main.py
```

### 3️⃣ n8n + Cloudflare Tunnel

```bash
cd ../infra/raspberry-pi
cp .env.example .env && nano .env
docker compose up -d
```

Panduan tunnel: [`infra/raspberry-pi/README.md`](infra/raspberry-pi/README.md)

### 4️⃣ Chatbot WhatsApp

Import `n8n/workflows/manajemen-stok-sayur-wa-pin.n8n.json`, pasang credential
Fonnte / Google Sheets / Groq, set `STOK_PIN`, aktifkan workflow, sambungkan
webhook ke Fonnte.

Detail: [`n8n/README.md`](n8n/README.md)

📖 **Panduan lengkap ujung-ke-ujung:** [`docs/SETUP.md`](docs/SETUP.md)

---

## ⚙️ Cara Kerja

### Alur penimbangan

1. Sayuran diletakkan di platform → load cell melentur
2. HX711 mengubah sinyal analog mV/V menjadi data digital 24-bit
3. `thread_berat` mengambil 5 sampel mentah per siklus, memangkas nilai ekstrem,
   mengambil median, lalu melewatkannya ke `WeightFilter`
4. Setelah 4 siklus stabil dalam toleransi ±200 g, nilai **dikunci** — layar berhenti
   berkedip seperti timbangan pasar sungguhan
5. Paralel, `thread_jenis` menjalankan inferensi YOLOv5 pada frame webcam; jenis
   dianggap sah setelah konsisten 8 frame berturut-turut
6. Tombol GPIO22 ditekan → foto diambil, di-encode base64, dikirim bersama berat dan
   jenis dalam **satu** POST ke Apps Script
7. Apps Script menyimpan foto ke Drive, menyisipkan baris baru ke Sheets berisi formula
   `HYPERLINK(...; IMAGE(...))` sehingga thumbnail langsung tampil di sel

### Alur chatbot

Pedagang kirim `LOGIN` → masukkan PIN → tanya bebas. n8n membaca sheet (dua kali:
mode nilai dan mode formula, agar link Drive bisa diekstrak), menyusun tabel teks,
mengirimkannya ke Groq bersama pertanyaan, lalu membalas via Fonnte.

Penjelasan tiap node: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 📊 Hasil Pengujian

Ringkasan dari BAB IV laporan Tugas Akhir:

| Pengujian | Bagian laporan |
|---|---|
| Kalibrasi | 4.4 |
| Akurasi dan presisi | 4.5 |
| Stabilitas pembacaan (drift) | 4.6 |
| Pengiriman data ke Google Sheets | 4.7 |
| Chatbot WhatsApp | 4.8 |

> Angka hasil pengujian mengacu pada unit referensi Tugas Akhir. Perangkat hasil
> replikasi akan menghasilkan angka berbeda dan **wajib dikalibrasi ulang**.

---

## 🔒 Keamanan

**Baca [`docs/SECURITY-NOTES.md`](docs/SECURITY-NOTES.md) sebelum menjalankan sistem
ini di lingkungan nyata.** Ringkasnya:

- **Endpoint Apps Script adalah endpoint tulis publik.** Di-deploy dengan akses
  "Anyone", siapa pun yang tahu URL `/exec` bisa menyisipkan baris ke Spreadsheet dan
  mengunggah berkas ke Google Drive Anda. Aktifkan `SHARED_TOKEN`.
- **Tidak ada rahasia yang di-hardcode** di repositori ini. Semua dibaca dari `.env`
  (perangkat) dan Script Properties (Apps Script).
- **PIN chatbot berlaku tunggal** untuk semua nomor, tanpa pembatasan percobaan.
- **Selalu sanitasi export n8n** sebelum commit — export memuat ID spreadsheet, path
  webhook, dan ID credential:

  ```bash
  python3 scripts/sanitize-workflow.py export-mentah.json n8n/workflows/keluaran.json
  ```

---

## 🗺️ Roadmap

**Perangkat**
- [ ] Buffer offline — simpan lokal saat jaringan putus, kirim ulang otomatis
- [ ] Kalibrasi multi-titik (saat ini satu titik)
- [ ] Kompensasi drift terhadap suhu
- [ ] Tambah kelas sayuran di luar tiga kelas awal
- [ ] Watchdog untuk memulihkan kamera yang menggantung

**Chatbot**
- [ ] PIN per-nomor dengan level akses
- [ ] Rate limiting percobaan PIN
- [ ] Input/koreksi data lewat WhatsApp
- [ ] Notifikasi otomatis stok menipis
- [ ] Laporan harian terjadwal

**Infrastruktur**
- [ ] Image Raspberry Pi siap pakai
- [ ] Pemantauan kesehatan perangkat
- [ ] Migrasi sesi n8n ke Redis

---

## 🤝 Kontribusi

Kontribusi terbuka lebar. Baca [`CONTRIBUTING.md`](CONTRIBUTING.md).

**Aturan utama:** jangan pernah commit `.env`, Deployment ID Apps Script, token, atau
export n8n mentah. CI akan menolaknya, tapi jangan mengandalkan CI — sekali rahasia
masuk riwayat Git, menghapusnya butuh `git filter-repo`.

---

## 📚 Sitasi

Bila karya ini membantu penelitian Anda:

```bibtex
@thesis{rahmady2026timbangan,
  title  = {Rancang Bangun Sistem Akuisisi Data Berat Sayuran
            Menggunakan Sensor Load Cell Berbasis Raspberry Pi CM4},
  author = {Rahmady, Reval Dino Try},
  year   = {2026},
  school = {Politeknik Negeri Sriwijaya},
  type   = {Laporan Akhir Diploma III},
  address= {Palembang, Indonesia}
}
```

Tersedia juga sebagai [`CITATION.cff`](CITATION.cff) — GitHub akan menampilkan tombol
"Cite this repository" secara otomatis.

---

## 📄 Lisensi

[MIT](LICENSE) — bebas dipakai, diubah, dan didistribusikan.

## 🙏 Terima Kasih

Dibangun dengan [n8n](https://n8n.io), [Fonnte](https://fonnte.com),
[Groq](https://groq.com), [YOLOv5](https://github.com/ultralytics/yolov5),
Google Apps Script, dan Google Sheets.

---

<sub>Dibuat untuk membantu pedagang pasar tradisional mencatat stok dengan alat yang
sudah mereka punya: timbangan dan WhatsApp.</sub>
