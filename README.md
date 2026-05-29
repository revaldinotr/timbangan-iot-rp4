<div align="center">

# 🌿 Timbangan IoT — Smart Vegetable Scale

**Timbangan digital berbasis Raspberry Pi 4 dengan deteksi jenis sayuran secara real-time menggunakan YOLOv5 TFLite, dilengkapi integrasi Google Sheets & Drive otomatis.**

[![Python](https://img.shields.io/badge/Python-3.9.2-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-C51A4A?style=flat-square&logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/)
[![TFLite](https://img.shields.io/badge/TFLite-2.13.0-FF6F00?style=flat-square&logo=tensorflow&logoColor=white)](https://www.tensorflow.org/lite)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9.0-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)

</div>

---

## 📋 Daftar Isi

1. [Fitur Utama](#-fitur-utama)
2. [Arsitektur Sistem](#-arsitektur-sistem)
3. [Komponen Hardware](#-komponen-hardware)
4. [Diagram Wiring](#-diagram-wiring)
5. [Struktur Project](#-struktur-project)
6. [Instalasi](#-instalasi)
7. [Konfigurasi](#-konfigurasi)
8. [Cara Menjalankan](#-cara-menjalankan)
9. [Kalibrasi Load Cell](#-kalibrasi-load-cell)
10. [Troubleshooting](#-troubleshooting)
11. [Lisensi & Kontak](#-lisensi--kontak)

---

## ✨ Fitur Utama

- ⚖️ **Pembacaan berat real-time** via HX711 load cell dengan median-filtering dan auto-tare drift correction
- 🥕 **Deteksi jenis sayuran** (Kentang · Tomat · Wortel) menggunakan YOLOv5 TFLite pada webcam
- 📺 **Tampilan LCD 16×2 I2C** yang menampilkan berat dan jenis sayuran secara live
- 📤 **Kirim data satu tombol** — foto + berat + jenis terkirim ke Google Sheets & Google Drive sekaligus
- ☁️ **Integrasi Google Apps Script** untuk logging otomatis ke spreadsheet dan penyimpanan foto di Drive
- 🔒 **Konfigurasi terpisah** — credential Google Script ID disimpan di `scripts/config.py` yang tidak di-commit ke Git
- 🛡️ **Thread-safe & race-free** — shutdown bersih via `threading.Event`, LCD dikontrol satu thread, kamera di-join sebelum release
- 📝 **Logging harian otomatis** ke `logs/main_YYYYMMDD.log`

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                      main.py (root)                         │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ thread_berat │  │ thread_jenis │  │ thread_lcd_      │  │
│  │              │  │              │  │ refresh          │  │
│  │ HX711 → kg   │  │ Cam → TFLite │  │                  │  │
│  │ Auto-tare    │  │ YOLOv5 infer │  │ Satu-satunya     │  │
│  │ 0.5s interval│  │ 2 FPS throttle│  │ penulis LCD      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └─────────────────┴──────── shared ────┘            │
│                           state (_lock)                     │
│                                │                            │
│                    ┌───────────▼──────────┐                 │
│                    │   Push Button GPIO22  │                 │
│                    │   Thread-Kirim        │                 │
│                    │   → capture foto      │                 │
│                    │   → kirim GAS (POST)  │                 │
│                    └──────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Komponen Hardware

| Komponen | Spesifikasi | Jumlah |
|---|---|---|
| Raspberry Pi 4 | Model B — 2GB / 4GB / 8GB RAM | 1 |
| Load Cell | 5 kg / 10 kg / 20 kg | 1 |
| Modul HX711 | ADC 24-bit untuk load cell | 1 |
| LCD 16×2 I2C | Dengan ekspander PCF8574 | 1 |
| Webcam USB | Min. 640×480, index 0 | 1 |
| Push Button | Tipe momentary (NO) | 1 |
| Kabel Jumper | Male-Female, Female-Female | secukupnya |
| MicroSD | Min. 16 GB + Raspberry Pi OS | 1 |

---

## 🔌 Diagram Wiring

### HX711 → Raspberry Pi 4

```
HX711          Raspberry Pi 4
──────         ───────────────
VCC    ───────  Pin 2  (5V)
GND    ───────  Pin 6  (GND)
DT     ───────  Pin 11 (GPIO17)
SCK    ───────  Pin 13 (GPIO27)
```

### LCD I2C 16×2 → Raspberry Pi 4

```
LCD I2C        Raspberry Pi 4
───────        ───────────────
VCC    ───────  Pin 4  (5V)
GND    ───────  Pin 9  (GND)
SDA    ───────  Pin 3  (GPIO2 / SDA1)
SCL    ───────  Pin 5  (GPIO3 / SCL1)
```

### Push Button → Raspberry Pi 4

```
Push Button    Raspberry Pi 4
───────────    ───────────────
Kaki 1 ───────  Pin 15 (GPIO22)
Kaki 2 ───────  Pin 14 (GND)

ℹ️  Pull-up internal aktif — tidak perlu resistor eksternal.
```

### Load Cell 4-Wire → HX711

```
Load Cell      HX711
─────────      ─────
Merah   ─────  E+  (Excitation +)
Hitam   ─────  E−  (Excitation −)
Hijau   ─────  A+  (Signal +)
Putih   ─────  A−  (Signal −)
```

---

## 📂 Struktur Project

```
timbangan-iot/
│
├── main.py                   # Entry point — jalankan dari sini
│
├── scripts/                  # Semua modul & konfigurasi
│   ├── config.py             # ⚠️  Credential & konfigurasi (TIDAK di-commit)
│   ├── config.example.py     # Template kosong — salin & isi sebelum menjalankan
│   └── .gitignore            # Melindungi config.py dari Git
│
├── model/
│   └── best-fp16.tflite      # Model YOLOv5 TFLite (unduh terpisah)
│
├── captures/                 # Foto hasil capture tombol (auto-managed)
├── logs/                     # Log harian: main_YYYYMMDD.log
│
├── .gitignore                # Gitignore root project
├── setup.sh                  # Script instalasi otomatis
└── README.md
```

> **Catatan:** `scripts/config.py` sudah terdaftar di `.gitignore` — file ini **tidak akan ikut ter-commit** ke repositori.

---

## 🚀 Instalasi

### Langkah 1 — Aktifkan I2C di Raspberry Pi

```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

Setelah reboot, verifikasi alamat LCD:

```bash
sudo i2cdetect -y 1
# Catat angka yang muncul (biasanya 27 atau 3f)
```

### Langkah 2 — Clone Repositori

```bash
git clone https://github.com/username/timbangan-iot.git
cd timbangan-iot
```

### Langkah 3 — Install Dependensi

**Cara cepat (gunakan setup script):**

```bash
chmod +x setup.sh
./setup.sh
```

**Cara manual:**

```bash
sudo apt update && sudo apt install -y python3-pip python3-smbus i2c-tools

pip3 install \
  hx711==1.0.0 \
  numpy==1.26.4 \
  opencv-python-headless==4.9.0.80 \
  requests==2.32.5 \
  RPi.GPIO==0.7.1 \
  rplcd==1.4.0 \
  tflite-runtime==2.13.0
```

**Versi lengkap dependensi Python:**

| Library | Versi | Fungsi |
|---|---|---|
| Python | 3.9.2 | Runtime |
| hx711 | 1.0.0 | Baca load cell ADC 24-bit |
| numpy | 1.26.4 | Array numerik & preprocessing |
| opencv-python-headless | 4.9.0.80 | Kamera & computer vision |
| requests | 2.32.5 | HTTP POST ke Google Apps Script |
| RPi.GPIO | 0.7.1 | Kontrol GPIO Raspberry Pi |
| rplcd | 1.4.0 | Driver LCD I2C 16×2 |
| tflite-runtime | 2.13.0 | Inferensi model YOLOv5 |

---

## ⚙️ Konfigurasi

### 1 — Buat file konfigurasi

```bash
cp scripts/config.example.py scripts/config.py
```

### 2 — Isi Google Apps Script ID

Buka [script.google.com](https://script.google.com), buat project baru, salin kode Apps Script dari `scripts/`, lalu deploy sebagai **Web App**:

- **Execute as:** Me
- **Who has access:** Anyone

Salin Script ID dari URL hasil deploy, lalu tempel di `scripts/config.py`:

```python
# scripts/config.py

GOOGLE_SHEETS_SCRIPT_ID = "AKfycb..."   # ← ganti dengan ID Anda
```

> 💡 Setiap kali deploy ulang GAS dan mendapat Script ID baru, **cukup edit baris ini saja** — tidak perlu menyentuh `main.py`.

### 3 — Sesuaikan konfigurasi hardware (jika perlu)

```python
# scripts/config.py

HX_DOUT            = 17      # GPIO pin DOUT HX711
HX_SCK             = 27      # GPIO pin SCK HX711
CALIBRATION_FACTOR = 23.7502 # ← ganti setelah kalibrasi
LCD_ADDR           = 0x27    # ← sesuaikan dengan hasil i2cdetect
BTN_PIN            = 22      # GPIO pin push button
```

---

## ▶️ Cara Menjalankan

### Jalankan langsung

```bash
python3 main.py
```

### Jalankan otomatis saat boot (systemd — disarankan)

```bash
sudo nano /etc/systemd/system/timbangan.service
```

Isi dengan:

```ini
[Unit]
Description=Timbangan IoT — Smart Vegetable Scale
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/timbangan-iot/main.py
WorkingDirectory=/home/pi/timbangan-iot
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

Aktifkan service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable timbangan
sudo systemctl start timbangan
sudo systemctl status timbangan   # pastikan Active: running
```

Perintah berguna lainnya:

```bash
sudo systemctl stop timbangan     # hentikan sementara
sudo systemctl restart timbangan  # restart
journalctl -u timbangan -f        # lihat log live
```

---

## 📐 Kalibrasi Load Cell

> ⚠️ Setiap load cell memiliki `CALIBRATION_FACTOR` yang berbeda. Wajib dikalibrasi sebelum digunakan.

```bash
python3 scripts/kalibrasi.py
```

Ikuti instruksi interaktif:

1. Pastikan timbangan **kosong** → tekan `ENTER` (tare otomatis)
2. Letakkan benda dengan berat yang **sudah diketahui** (contoh: 500 gram)
3. Masukkan angka beratnya saat diminta
4. Script akan menampilkan nilai `CALIBRATION_FACTOR` yang tepat
5. Update nilai tersebut di `scripts/config.py`:

```python
CALIBRATION_FACTOR = 23.7502   # ← ganti dengan hasil kalibrasi Anda
```

---

## 🔍 Troubleshooting

| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| LCD tidak tampil | Alamat I2C salah | Jalankan `sudo i2cdetect -y 1`, sesuaikan `LCD_ADDR` di `config.py` |
| LCD tampil karakter aneh | Charmap tidak cocok | Coba ganti `charmap='A00'` di `lcd_init()` |
| Berat selalu 0 | Wiring HX711 salah | Periksa koneksi DOUT→GPIO17 dan SCK→GPIO27 |
| Berat tidak stabil | Getaran / noise | Jauhkan dari getaran, naikkan `NOISE_THRESHOLD_KG` |
| Berat tidak akurat | Kalibrasi belum dilakukan | Jalankan `python3 scripts/kalibrasi.py` |
| Deteksi jenis tidak muncul | Model tidak ditemukan | Pastikan `model/best-fp16.tflite` ada |
| Webcam tidak terdeteksi | Index salah | Coba ganti `WEBCAM_INDEX = 1` dst. di `config.py` |
| Gagal kirim ke Google | Koneksi / Script ID salah | Cek `ping google.com`, periksa `GOOGLE_SHEETS_SCRIPT_ID` di `config.py` |
| Error `config.py not found` | Belum salin template | Jalankan `cp scripts/config.example.py scripts/config.py` |
| Error `RPi.GPIO` | Permission GPIO | Jalankan dengan `sudo python3 main.py` |
| Error `hx711 not found` | Library belum install | Jalankan `pip3 install hx711==1.0.0` |
| Tombol tidak respons | Wiring atau GPIO salah | Pastikan kaki button ke GPIO22 dan GND, cek `BTN_PIN` di `config.py` |

---

## 📄 Lisensi & Kontak


---

<div align="center">

Dibuat dengan ❤️ menggunakan Raspberry Pi 4 + Python

</div>
