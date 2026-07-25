# Pemecahan Masalah — Perangkat

Untuk masalah chatbot WhatsApp, lihat
[`TROUBLESHOOTING-CHATBOT.md`](TROUBLESHOOTING-CHATBOT.md).

---

## Program tidak mau jalan

### `[ERROR] GAS_SCRIPT_ID belum diatur`

`device/.env` belum dibuat atau `GAS_SCRIPT_ID` masih kosong.

```bash
cd device && cp .env.example .env && nano .env
```

### `RPi.GPIO tidak ditemukan`

```bash
pip install RPi.GPIO
```

Bila Anda memakai virtualenv, pastikan sudah `source .venv/bin/activate`.

### `tflite-runtime atau tensorflow tidak ditemukan`

`tflite-runtime` tidak tersedia lewat `pip install` biasa untuk semua kombinasi
Python/arsitektur. Pasang dari wheel yang sesuai, atau gunakan `tensorflow` sebagai
alternatif (jauh lebih berat).

### `[WARN] RPLCD tidak terinstall`

Peringatan, bukan error — program tetap jalan tanpa LCD.

```bash
pip install RPLCD smbus2
```

---

## Masalah pembacaan berat

### Angka melompat-lompat tak karuan

Urutan pemeriksaan, dari penyebab tersering:

1. **Sambungan kabel** — kabel load cell ke HX711 longgar. Ini penyebab nomor satu.
2. **EMI** — jauhkan dari adaptor switching, motor, dan kabel daya.
3. **Getaran mekanik** — meja goyang, kipas menempel di casing.
4. **Panjang kabel** — kabel load cell yang panjang menangkap lebih banyak derau.
5. **Catu daya** — 5 V yang tidak stabil membuat HX711 ikut tidak stabil.

Tambahkan kapasitor 100 nF antara VCC dan GND dekat modul HX711 bila masih berderau.

Diagnostik: jalankan `python3 calibrate.py` dan perhatikan angka sebaran pada titik
nol. Di atas 5000 menandakan masalah perangkat keras, bukan perangkat lunak.

### Selalu menampilkan 0,00 kg

- Beban di bawah `DEADBAND_KG` (0,05 kg) memang dibaca sebagai nol
- `CALIBRATION_FACTOR` sangat keliru — kalibrasi ulang
- Load cell tidak menerima beban: periksa apakah platform benar-benar menekan sensor
- Kabel A+/A− terbalik atau putus

### Berat berlawanan arah (bertambah beban, angka mengecil)

Polaritas load cell terbalik. Dua pilihan: biarkan `CALIBRATION_FACTOR` bernilai
negatif, atau tukar kabel A+ dengan A− lalu kalibrasi ulang.

### Angka menyimpang konsisten

Kalibrasi ulang. Bila error membesar seiring bertambahnya beban, penyebabnya
mekanik melentur atau load cell dipakai jauh di bawah kapasitasnya — lihat
[`CALIBRATION.md`](CALIBRATION.md).

### Nilai terkunci dan tidak mau berubah

Stable lock sedang aktif. Kunci dilepas bila berat berubah ≥ 1 kg atau turun di bawah
0,15 kg. Untuk penggunaan dengan selisih beban kecil, turunkan
`LOCK_RELEASE_DELTA_KG` di `main.py`.

---

## Masalah LCD

### LCD kosong / hanya kotak-kotak

1. Cek alamat: `sudo i2cdetect -y 1`
2. Sesuaikan `LCD_ADDR` di `main.py` (umumnya `0x27` atau `0x3F`)
3. Putar potensiometer kontras di belakang modul LCD
4. Pastikan LCD diberi **5 V**, bukan 3,3 V

### Karakter acak

Biasanya konflik akses I2C. Pastikan hanya `thread_lcd_refresh` yang menulis ke LCD —
jangan menambahkan pemanggilan `lcd.write_string()` dari thread lain.

---

## Masalah kamera

### Kamera tidak terbuka

```bash
ls /dev/video*
v4l2-ctl --list-formats-ext -d /dev/video0
```

Bila webcam bukan di indeks 0, ubah `WEBCAM_INDEX` di `main.py`.

### Deteksi tidak pernah muncul

1. **Model tidak ada** — pastikan `device/model/best-fp32.tflite` benar-benar ada
2. **Pencahayaan** — model dilatih pada kondisi tertentu; cahaya sangat berbeda
   menurunkan akurasi drastis
3. **Jarak objek** — terlalu jauh membuat objek terlalu kecil setelah resize ke 640
4. **Urutan kelas** — `CLASS_NAMES` harus sama persis dengan urutan saat pelatihan

Turunkan `CONF_THRESH` untuk menguji apakah model mendeteksi sama sekali. Nilai
bawaan 0,08 sudah sangat rendah; bila tetap nihil, kemungkinan modelnya yang
bermasalah.

### Deteksi berkedip ganti-ganti

Naikkan `CONFIRM_FRAMES` (bawaan 8). Trade-off: konfirmasi lebih lambat.

### Inferensi lambat

- Gunakan model FP16, bukan FP32
- Turunkan `WEBCAM_WIDTH`/`WEBCAM_HEIGHT` ke 640×480
- Pastikan `NUM_THREADS=4` (CM4 punya 4 core)
- Periksa throttling termal: `vcgencmd measure_temp`

---

## Masalah pengiriman data

### `✗ Tidak terhubung — cek WiFi/LAN`

```bash
ping -c 3 script.google.com
```

### `✗ Timeout`

Foto base64 terlalu besar untuk koneksi yang lambat. Turunkan `JPEG_QUALITY`
di `main.py` (bawaan 70).

### `✗ GAS error: Unauthorized`

`GAS_SHARED_TOKEN` di `.env` tidak cocok dengan Script Property `SHARED_TOKEN`.
Periksa keduanya — perhatikan spasi tersembunyi di awal/akhir.

### `✗ HTTP 401` atau `HTTP 403`

Deployment Apps Script tidak diset ke **Anyone**. Buka
**Deploy → Manage deployments** dan periksa pengaturannya.

### Data masuk tapi foto tidak

1. Periksa kuota Drive
2. Jalankan `testScript()` di Apps Script untuk mengisolasi masalah
3. Lihat log eksekusi Apps Script: **Executions** di panel kiri

### Thumbnail tidak tampil di sel

Formula memakai titik koma sebagai pemisah argumen (locale Indonesia). Bila
spreadsheet Anda memakai locale yang menuntut koma, ubah di `pb_to_sheets.gs`.

---

## Masalah systemd

### Service gagal start

```bash
sudo journalctl -u timbangan -n 50 --no-pager
```

Penyebab tersering: path di `WorkingDirectory` dan `ExecStart` tidak sesuai lokasi
repo Anda.

### Service jalan tapi GPIO error

Pastikan user pada unit file punya akses perangkat keras:

```
SupplementaryGroups=gpio i2c video
```

### Virtualenv tidak terpakai

Arahkan `ExecStart` ke interpreter di dalam virtualenv:

```
ExecStart=/home/pi/timbangan-iot-rp4/device/.venv/bin/python3 /home/pi/timbangan-iot-rp4/device/main.py
```

---

## Masih bermasalah?

Buka [issue](../../issues) dengan menyertakan:

- Langkah reproduksi
- Keluaran `journalctl -u timbangan -n 50` atau log terminal
- Versi Raspberry Pi OS dan Python
- Foto wiring bila masalahnya perangkat keras

⚠️ **Sensor Deployment ID, token, dan nomor WhatsApp** sebelum menempel log.
