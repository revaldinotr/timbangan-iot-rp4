# Panduan Instalasi Ujung-ke-Ujung

Perkiraan waktu: **2–3 jam** untuk pemasangan pertama, di luar perakitan mekanik.

Sistem punya empat bagian. Pasang berurutan — tiap bagian bisa diuji sendiri sebelum
lanjut, sehingga bila ada masalah Anda tahu persis di mana letaknya.

```
1. Google Sheets + Apps Script   ← mulai di sini (bisa diuji tanpa hardware)
2. Perangkat Raspberry Pi
3. n8n + Cloudflare Tunnel
4. Chatbot WhatsApp
```

---

## Bagian 1 — Google Sheets + Apps Script

### 1.1 Buat spreadsheet

Buat spreadsheet baru di [sheets.google.com](https://sheets.google.com). Header
dibuat otomatis pada pengiriman pertama, jadi biarkan kosong.

Salin ID dari URL — nanti dibutuhkan di Bagian 4:

```
https://docs.google.com/spreadsheets/d/1AbCdEfGh.../edit
                                       └── ID ──┘
```

### 1.2 Tempel skrip

**Extensions → Apps Script**, hapus isi bawaan, tempel seluruh isi
`apps-script/pb_to_sheets.gs`, simpan.

### 1.3 Aktifkan token bersama

```bash
openssl rand -hex 24
```

**Project Settings → Script Properties → Add script property**

| Property | Value |
|---|---|
| `SHARED_TOKEN` | hasil perintah di atas |

Simpan token ini — akan dipakai lagi di Bagian 2.

### 1.4 Deploy

**Deploy → New deployment → Web app**

| Pengaturan | Nilai |
|---|---|
| Execute as | Me |
| Who has access | Anyone |

Salin **Deployment ID** dari URL hasil deploy.

### 1.5 Uji tanpa hardware

Jalankan fungsi `testScript()` di editor. Google akan meminta izin Drive dan
Spreadsheet pada eksekusi pertama.

✅ **Berhasil bila:** satu baris muncul di sheet dan satu berkas ada di folder Drive
`Captures Data Sayur`.

---

## Bagian 2 — Perangkat Raspberry Pi

### 2.1 Siapkan OS

Flash Raspberry Pi OS 64-bit, aktifkan SSH, lalu sambungkan ke jaringan.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git i2c-tools v4l-utils
```

Aktifkan I2C:

```bash
sudo raspi-config     # Interface Options → I2C → Enable
sudo reboot
```

### 2.2 Verifikasi hardware

```bash
sudo i2cdetect -y 1   # LCD harus muncul, umumnya di 0x27 atau 0x3F
ls /dev/video*        # webcam harus muncul sebagai /dev/video0
```

Bila alamat LCD berbeda, sesuaikan `LCD_ADDR` di `device/main.py`.
Wiring lengkap: [`HARDWARE.md`](HARDWARE.md)

### 2.3 Pasang program

```bash
git clone https://github.com/revaldinotr/timbangan-iot-rp4.git
cd timbangan-iot-rp4/device

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`tflite-runtime` perlu dipasang terpisah sesuai versi Python dan arsitektur Anda —
lihat catatan di `requirements.txt`.

### 2.4 Konfigurasi

```bash
cp .env.example .env
nano .env
```

Isi:

```
GAS_SCRIPT_ID=<Deployment ID dari langkah 1.4>
GAS_SHARED_TOKEN=<token dari langkah 1.3>
```

### 2.5 Siapkan model

Letakkan model di `device/model/best-fp32.tflite`.
Panduan pelatihan dan export: [`../device/model/README.md`](../device/model/README.md)

### 2.6 Kalibrasi — WAJIB

Faktor bawaan berasal dari unit referensi dan **tidak akan cocok** untuk perangkat
Anda.

```bash
python3 calibrate.py
```

Siapkan beban acuan yang massanya pasti (anak timbangan, atau air kemasan bersegel).
Salin hasilnya ke `.env`:

```
CALIBRATION_FACTOR=<hasil kalibrasi Anda>
```

Detail: [`CALIBRATION.md`](CALIBRATION.md)

### 2.7 Jalankan

```bash
python3 main.py
```

✅ **Berhasil bila:** splash screen tampil di LCD, lalu berat dan jenis muncul
realtime. Tekan tombol → satu baris baru masuk ke spreadsheet lengkap dengan
thumbnail foto.

### 2.8 Jalankan otomatis saat boot

```bash
sudo cp systemd/timbangan.service /etc/systemd/system/
sudo nano /etc/systemd/system/timbangan.service   # sesuaikan path bila perlu
sudo systemctl daemon-reload
sudo systemctl enable --now timbangan
sudo journalctl -u timbangan -f
```

---

## Bagian 3 — n8n + Cloudflare Tunnel

Ikuti [`../infra/raspberry-pi/README.md`](../infra/raspberry-pi/README.md).

Ringkasnya:

1. Buat tunnel di Cloudflare Zero Trust, catat token
2. Pasang `cloudflared` di Raspberry Pi, jalankan `service install <token>`
3. Arahkan subdomain ke `localhost:5678`
4. `cp .env.example .env`, isi, lalu `docker compose up -d`

✅ **Berhasil bila:** `https://n8n.domainanda.com` terbuka dan menampilkan setup n8n.

> Bila CM4 2 GB terasa berat karena juga menjalankan kamera dan inferensi,
> pertimbangkan menjalankan n8n di perangkat terpisah.

---

## Bagian 4 — Chatbot WhatsApp

### 4.1 Siapkan Fonnte

1. Daftar di [fonnte.com](https://fonnte.com)
2. **Add Device** → pindai QR dengan nomor WhatsApp bot
3. Salin **Token** device

> Gunakan nomor terpisah untuk bot, bukan nomor pribadi Anda.

### 4.2 Siapkan Groq

Buat API key di [console.groq.com/keys](https://console.groq.com/keys).

### 4.3 Import workflow

n8n → **Workflows** → **Import from File** →
`n8n/workflows/manajemen-stok-sayur-wa-pin.n8n.json`

### 4.4 Buat credential

| Nama | Tipe | Isi |
|---|---|---|
| Google Sheets account | Google Sheets OAuth2 API | ikuti wizard OAuth |
| Header Auth account | Header Auth | Name `Authorization`, Value token Fonnte |
| Groq account | Groq API | API key Groq |

### 4.5 Isi nilai spesifik

Ganti `YOUR_GOOGLE_SHEET_ID` di node **Ambil Data Sheets** dan **Ambil Link Foto**
dengan ID dari langkah 1.1. Pilih credential yang sesuai di tiap node
(daftar lengkap di [`../n8n/README.md`](../n8n/README.md)).

### 4.6 Set PIN

Isi `STOK_PIN` di `infra/raspberry-pi/.env`, lalu `docker compose up -d` ulang.
Minimal 6 digit.

### 4.7 Sambungkan webhook

Aktifkan workflow → salin **Production URL** dari node `WhatsApp Webhook` → tempel ke
Fonnte → **Device** → **Webhook URL**.

### 4.8 Uji

Kirim `LOGIN` ke nomor bot dari WhatsApp Anda.

✅ **Berhasil bila:** bot meminta PIN, menerima PIN yang benar, lalu bisa menjawab
`stok tomat berapa?` dengan data dari spreadsheet.

---

## Checklist Akhir

**Fungsional**
- [ ] `testScript()` Apps Script berhasil
- [ ] LCD menampilkan berat realtime
- [ ] Deteksi jenis sayur bekerja
- [ ] Tombol mengirim data + foto ke Sheets
- [ ] Thumbnail foto tampil di sel spreadsheet
- [ ] Panel n8n dapat diakses lewat HTTPS
- [ ] Alur login PIN WhatsApp berjalan
- [ ] Bot menjawab pertanyaan data
- [ ] Bot mengirim link foto

**Keamanan** — lihat [`SECURITY-NOTES.md`](SECURITY-NOTES.md)
- [ ] `SHARED_TOKEN` aktif dan cocok di kedua sisi
- [ ] `STOK_PIN` minimal 6 digit lewat environment variable
- [ ] Basic auth n8n aktif
- [ ] `N8N_ENCRYPTION_KEY` dicadangkan di luar perangkat
- [ ] Tidak ada `.env` yang ter-commit
- [ ] `bash scripts/check-secrets.sh` bersih

Ada masalah? → [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
