# Perangkat Keras — BOM, Pinout, dan Wiring

## Daftar Komponen (BOM)

| # | Komponen | Spesifikasi | Jml |
|---|---|---|---|
| 1 | Raspberry Pi Compute Module 4 | 64-bit, 2 GB LPDDR4 | 1 |
| 2 | CM4 IO Board | atau carrier board setara | 1 |
| 3 | Load cell | 180 kg, 1,0–2,0 mV/V, strain gauge full bridge | 1 |
| 4 | Modul HX711 | ADC 24-bit | 1 |
| 5 | LCD karakter 16×2 | dengan backpack I2C (PCF8574) | 1 |
| 6 | USB webcam | disarankan mendukung 1280×720 | 1 |
| 7 | Push button | momentary, normally open | 1 |
| 8 | Power supply | 110–220 VAC → 5 VDC 3 A | 1 |
| 9 | Kabel jumper, terminal, casing | secukupnya | — |

---

## Peta Pin GPIO (penomoran BCM)

| Fungsi | Pin BCM | Pin fisik | Keterangan |
|---|---|---|---|
| HX711 DOUT | GPIO17 | 11 | Data keluar dari HX711 |
| HX711 SCK | GPIO27 | 13 | Clock ke HX711 |
| Push button | GPIO22 | 15 | Aktif rendah, pull-up internal |
| LCD SDA | GPIO2 | 3 | I2C data |
| LCD SCL | GPIO3 | 5 | I2C clock |
| 5 V | — | 2 / 4 | Catu HX711 dan LCD |
| GND | — | 6 / 9 / 14 | Ground bersama |

Pin HX711 dapat diubah lewat `device/.env` (`HX_DOUT`, `HX_SCK`).

---

## Wiring

### Load cell → HX711

Warna kabel mengikuti konvensi umum; **selalu cek datasheet load cell Anda**.

| Kabel load cell | Terminal HX711 |
|---|---|
| Merah — E+ | E+ |
| Hitam — E− | E− |
| Putih — A− | A− |
| Hijau — A+ | A+ |

> Bila hasil pembacaan berlawanan arah (beban ditambah tetapi angka mengecil),
> tukar A+ dengan A−, atau biarkan `CALIBRATION_FACTOR` bernilai negatif.

### HX711 → Raspberry Pi

| HX711 | Raspberry Pi |
|---|---|
| VCC | 5 V (pin 2) |
| GND | GND (pin 6) |
| DT (DOUT) | GPIO17 (pin 11) |
| SCK | GPIO27 (pin 13) |

### LCD I2C → Raspberry Pi

| LCD | Raspberry Pi |
|---|---|
| VCC | 5 V (pin 4) |
| GND | GND (pin 9) |
| SDA | GPIO2 (pin 3) |
| SCL | GPIO3 (pin 5) |

Cari alamat I2C modul Anda:

```bash
sudo apt install -y i2c-tools
sudo i2cdetect -y 1
```

Umumnya `0x27` atau `0x3F`. Sesuaikan `LCD_ADDR` di `main.py` bila berbeda.

### Push button → Raspberry Pi

```
GPIO22 (pin 15) ──┬── [ TOMBOL ] ── GND (pin 14)
                  │
             pull-up internal
```

Resistor eksternal tidak diperlukan — pull-up internal sudah diaktifkan
di `btn_setup()`. Debounce ditangani perangkat lunak (300 ms).

---

## Mengaktifkan I2C

```bash
sudo raspi-config
# Interface Options → I2C → Enable
sudo reboot
```

Verifikasi:

```bash
ls /dev/i2c-*        # harus muncul /dev/i2c-1
```

---

## Verifikasi Kamera

```bash
ls /dev/video*                              # harus ada /dev/video0
v4l2-ctl --list-formats-ext -d /dev/video0  # cek resolusi yang didukung
```

Bila webcam terdeteksi bukan pada indeks 0, ubah `WEBCAM_INDEX` di `main.py`.

---

## Catatan Pemasangan Mekanik

Kestabilan pembacaan lebih banyak ditentukan mekanik daripada perangkat lunak:

- **Pasang load cell kokoh.** Dudukan yang lentur menimbulkan drift dan getaran.
- **Beban harus terpusat.** Beban di tepi platform menghasilkan pembacaan berbeda
  dari beban di tengah.
- **Hindari sumber EMI.** Adaptor switching, motor, dan kabel daya yang berdekatan
  menimbulkan spike pada HX711.
- **Kabel load cell sependek mungkin.** Kabel panjang menangkap lebih banyak derau.
- **Beri celah bebas.** Platform tidak boleh menyentuh casing di titik mana pun,
  karena gesekan membuat pembacaan tidak kembali ke nol.

Bila sebaran pembacaan tetap besar setelah semua di atas dipenuhi, tambahkan
kapasitor 100 nF antara VCC dan GND di dekat modul HX711.
