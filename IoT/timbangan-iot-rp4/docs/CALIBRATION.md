# Kalibrasi Load Cell

## Mengapa Wajib

`CALIBRATION_FACTOR` menerjemahkan angka mentah HX711 menjadi satuan gram:

```
gram = (nilai_mentah − nilai_tare) / CALIBRATION_FACTOR
```

Faktor ini bergantung pada:

- Sensitivitas load cell (mV/V) dan kapasitas maksimumnya
- Penguatan modul HX711 (umumnya 128× pada kanal A)
- Rasio mekanik dudukan dan platform
- Toleransi produksi tiap unit

Artinya: **faktor perangkat lain tidak akan cocok untuk perangkat Anda.** Nilai
bawaan `24.1850` di repositori ini berasal dari unit referensi Tugas Akhir dan
disediakan hanya sebagai contoh format.

---

## Prosedur

### 1. Siapkan beban acuan

Gunakan massa yang sudah pasti diketahui:

- Anak timbangan (paling ideal)
- Air kemasan bersegel — 1 liter ≈ 1000 g
- Beras kemasan pabrik yang belum dibuka

Pilih massa yang mendekati kisaran kerja timbangan. Untuk timbangan sayur
1–5 kg, beban acuan 1–2 kg sudah memadai.

### 2. Jalankan skrip

```bash
cd device
python3 calibrate.py
```

Skrip akan memandu tiga tahap:

1. **Titik nol** — platform dikosongkan, skrip membaca nilai tare
2. **Beban acuan** — beban diletakkan, Anda memasukkan massanya dalam gram
3. **Hasil** — faktor dihitung dan ditampilkan

### 3. Simpan hasilnya

```
CALIBRATION_FACTOR=24.1850
```

Masukkan ke `device/.env`, lalu jalankan ulang `main.py`.

---

## Membaca Hasil

| Indikator | Arti |
|---|---|
| Sebaran titik nol < 1000 | Sangat baik |
| Sebaran 1000–5000 | Wajar |
| Sebaran > 5000 | Ada masalah — periksa kabel, EMI, getaran |
| Faktor negatif | Polaritas terbalik; boleh dipakai, atau tukar A+/A− |
| Selisih < 1000 | Beban tidak terbaca — periksa mekanik dan sambungan |

---

## Verifikasi

Setelah kalibrasi, uji dengan beban **berbeda** dari yang dipakai kalibrasi:

| Beban acuan | Pembacaan | Selisih | Error |
|---|---|---|---|
| 500 g | | | |
| 1000 g | | | |
| 2000 g | | | |
| 5000 g | | | |

Hitung error relatif:

```
error (%) = |pembacaan − sebenarnya| / sebenarnya × 100
```

Untuk timbangan pasar, error di bawah 1 % umumnya sudah memadai.

---

## Bila Hasil Tidak Linear

Kalibrasi satu titik mengasumsikan hubungan linear antara beban dan keluaran.
Bila error membesar seiring bertambahnya beban, penyebab tersering:

1. **Mekanik melentur** pada beban besar — perkuat dudukan
2. **Load cell melampaui kapasitas** — kapasitas 180 kg dipakai untuk beban 1 kg
   berarti hanya memakai 0,5 % rentangnya, sehingga resolusi efektif rendah
3. **Beban tidak terpusat** — uji ulang dengan posisi yang konsisten

> **Catatan pemilihan sensor.** Load cell 180 kg untuk menimbang sayuran 1–5 kg
> memang jauh melampaui kebutuhan. Load cell 5 kg atau 10 kg akan memberi resolusi
> jauh lebih halus untuk rentang tersebut. Ini salah satu arah pengembangan yang
> layak dicoba oleh kontributor.

Kalibrasi multi-titik ada di roadmap.

---

## Kapan Perlu Kalibrasi Ulang

- Setelah membongkar atau memasang ulang mekanik
- Setelah mengganti load cell atau modul HX711
- Bila pembacaan mulai menyimpang konsisten
- Setelah perpindahan lokasi dengan perbedaan suhu ekstrem
- Sebagai rutinitas — sekali setiap beberapa bulan
