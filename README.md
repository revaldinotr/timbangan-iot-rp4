# TIMBANGAN DIGITAL - Raspberry Pi 4
### Raspberry Pi 4 (Python)

---

## DAFTAR ISI
1. [Komponen yang Dibutuhkan](#komponen)
2. [Diagram Wiring GPIO](#wiring)
3. [Perbandingan Pin ESP32 vs RPi4](#perbandingan)
4. [Instalasi Library](#instalasi)
5. [Konfigurasi Google Apps Script](#google-script)
6. [Cara Menjalankan](#menjalankan)
7. [Kalibrasi Load Cell](#kalibrasi)
8. [Troubleshooting](#troubleshooting)

---

## 1. KOMPONEN YANG DIBUTUHKAN <a name="komponen"></a>

| Komponen | Spesifikasi | Jumlah |
|---|---|---|
| Raspberry Pi 4 | Model B (2GB/4GB/8GB RAM) | 1 |
| Load Cell | 5kg / 10kg / 20kg | 1 |
| HX711 | Modul ADC Load Cell | 1 |
| LCD 16x2 | Dengan modul I2C (PCF8574) | 1 |
| Push Button | Tipe momentary (NO) | 1 |
| Resistor | 10kΩ (opsional, sudah ada pull-up internal) | 1 |
| Kabel Jumper | Male-Female, Female-Female | secukupnya |
| MicroSD | Min. 8GB + Raspberry Pi OS | 1 |

---

## 2. DIAGRAM WIRING GPIO <a name="wiring"></a>

### A. HX711 → Raspberry Pi 4

```
HX711          Raspberry Pi 4
------         ---------------
VCC    ───────  Pin 2  (5V Power)
GND    ───────  Pin 6  (GND)
DT     ───────  Pin 11 (GPIO17)
SCK    ───────  Pin 13 (GPIO27)
```

### B. LCD I2C 16x2 → Raspberry Pi 4

```
LCD I2C        Raspberry Pi 4
-------        ---------------
VCC    ───────  Pin 4  (5V Power)
GND    ───────  Pin 9  (GND)
SDA    ───────  Pin 3  (GPIO2 / SDA1)
SCL    ───────  Pin 5  (GPIO3 / SCL1)
```

### C. Push Button → Raspberry Pi 4

```
Push Button    Raspberry Pi 4
-----------    ---------------
Kaki 1 ───────  Pin 15 (GPIO22)
Kaki 2 ───────  Pin 14 (GND)

CATATAN: Sudah ada internal pull-up di GPIO23.
         Tidak perlu resistor eksternal.
```

### D. Layout Pin Raspberry Pi 4 (yang dipakai):

```
                 3V3  (1) (2)  5V  ← LCD & HX711 VCC
          SDA1 GPIO2  (3) (4)  
          SCL1 GPIO3  (5) (6)  GND 
                      (7) (8)
                  GND (9)(10)
                     (11)(12)  GPIO17  ← HX711 DT/DOUT
                     (13)(14)  HX711 SCK GPIO27
                     (15)(16)  GPIO22  ← Push Button
                     (17)(18)
                     (19)(20)
                     (21)(22)
                     (23)(24)
                     (25)(26)
                     (27)(28)
                     (29)(30)
                     (31)(32)
                     (35)(34)
```

### E. Wiring Load Cell ke HX711:

Load cell 4-wire (warna kabel umum):
```
Load Cell      HX711
---------      -----
Merah   ───── E+  (Excitation +)
Hitam   ───── E-  (Excitation -)
Hijau   ───── A+  (Signal +)
Putih   ───── A-  (Signal -)
```

---
## 3. INSTALASI LIBRARY <a name="instalasi"></a>

### Langkah 1: Aktifkan I2C di Raspberry Pi

```bash
sudo raspi-config
# Pilih: Interface Options → I2C → Enable → Yes
# Atau jalankan otomatis:
sudo raspi-config nonint do_i2c 0
```

Reboot setelah mengaktifkan I2C:
```bash
sudo reboot
```

### Langkah 2: Install semua library (cara mudah)

```bash
chmod +x setup.sh
./setup.sh
```

### Langkah 3: Install manual (jika script tidak berjalan)

```bash
sudo apt update
sudo apt install -y python3-pip python3-smbus i2c-tools
pip3 install RPi.GPIO
pip3 install hx711
pip3 install RPLCD
pip3 install requests
```

### Langkah 4: Cek alamat I2C LCD

```bash
sudo i2cdetect -y 1
```

Anda akan melihat angka `27` atau `3f` pada output. Default biasanya `0x27`. Jika berbeda, ubah di `timbangan.py`:

```python
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,  # ← Ubah sesuai hasil i2cdetect
    ...
)
```

---

## 4. KONFIGURASI GOOGLE APPS SCRIPT <a name="google-script"></a>

Pastikan Web App sudah di-deploy dengan pengaturan:
- **Execute as:** Me
- **Who has access:** Anyone

Jika ingin membuat baru:
1. Buka [script.google.com](https://script.google.com)
2. Buat project baru
3. Salin kode Apps Script pada directory scripts
4. Deploy → New deployment → Web App
5. Salin ID dari URL dan update `GOOGLE_SCRIPT_ID` di `config.py`

---

## 6. CARA MENJALANKAN <a name="menjalankan"></a>

### Jalankan program:
```bash
python3 timbangan.py
```

### Jalankan otomatis saat boot:
```bash
sudo nano /etc/rc.local
# Tambahkan sebelum "exit 0":
python3 /home/pi/timbangan_rpi4/timbangan.py &
```

### Jalankan sebagai service (lebih profesional):
```bash
sudo nano /etc/systemd/system/timbangan.service
```

Isi file:
```ini
[Unit]
Description=Timbangan Digital
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/timbangan_rpi4/timbangan.py
WorkingDirectory=/home/pi/timbangan_rpi4
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Aktifkan:
```bash
sudo systemctl enable timbangan
sudo systemctl start timbangan
sudo systemctl status timbangan
```

---

## 7. KALIBRASI LOAD CELL <a name="kalibrasi"></a>

`CALIBRATION_FACTOR = ...` **Setiap load cell berbeda**

```bash
python3 scripts/kalibrasi.py
```

Ikuti instruksi di layar:
1. Pastikan load cell kosong → tekan ENTER (tare)
2. Letakkan benda dengan berat diketahui (misalnya 500 gram)
3. Masukkan angka beratnya
4. Program akan menghitung `CALIBRATION_FACTOR` yang tepat
5. Update nilai tersebut di `timbangan.py`

---

## 8. TROUBLESHOOTING <a name="troubleshooting"></a>

| Masalah | Solusi |
|---|---|
| LCD tidak tampil | Cek alamat I2C dengan `sudo i2cdetect -y 1`, sesuaikan `address` di kode |
| LCD tampil karakter aneh | Coba ganti `charmap='A00'` di inisialisasi LCD |
| Berat selalu 0 | Cek wiring HX711, pastikan kabel load cell benar |
| Berat tidak stabil | Jauhkan dari getaran, turunkan nilai `NOISE_THRESHOLD_KG` |
| Berat tidak akurat | Jalankan `kalibrasi.py` dan update `CALIBRATION_FACTOR` |
| Gagal kirim ke Google | Cek koneksi internet: `ping google.com` |
| Error RPi.GPIO | Jalankan dengan `sudo python3 timbangan.py` |
| Error `hx711 not found` | Jalankan `pip3 install hx711` |
| Tombol tidak respons | Cek wiring GPIO23, pastikan ke GND saat ditekan |

---
