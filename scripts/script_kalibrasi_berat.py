#!/usr/bin/env python3
"""
============================================
  KALIBRASI LOAD CELL - tatobari/hx711 API
  
  Jalankan SEBELUM program utama untuk
  mendapatkan CALIBRATION_FACTOR yang tepat.
  
  Cara:  python3 kalibrasi.py
============================================
"""

import RPi.GPIO as GPIO
import time
import statistics
from hx711 import HX711

HX_DOUT = 17
HX_SCK  = 27

def read_avg(hx, n=15):
    """Ambil rata-rata n pembacaan raw."""
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        if raw is not False and raw is not None:
            vals.append(raw)
        time.sleep(0.05)
    if not vals:
        return None
    return statistics.median(vals)

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    print("=" * 50)
    print("  KALIBRASI LOAD CELL HX711")
    print("  (Library: tatobari/hx711)")
    print("=" * 50)

    hx = HX711(HX_DOUT, HX_SCK)

    # ── Tare ──
    print("\nPastikan load cell KOSONG (tidak ada benda).")
    input("Tekan ENTER untuk mulai tare...")

    print(f"Mengambil sampel tare...", end="", flush=True)
    tare_raw = read_avg(hx, 20)
    if tare_raw is None:
        print("\nERROR: Gagal baca HX711. Cek wiring!")
        GPIO.cleanup()
        return
    print(f" selesai. Raw tare = {tare_raw:.0f}")

    # ── Benda acuan ──
    print("\nLetakkan benda dengan berat DIKETAHUI di atas load cell.")
    try:
        berat_acuan_gram = float(input("Masukkan berat benda acuan dalam GRAM (contoh: 500): "))
    except ValueError:
        print("Input tidak valid!")
        GPIO.cleanup()
        return

    input("\nBenda sudah diletakkan? Tekan ENTER untuk mulai membaca...")
    time.sleep(0.5)

    print(f"Mengambil sampel benda acuan...", end="", flush=True)
    benda_raw = read_avg(hx, 20)
    if benda_raw is None:
        print("\nERROR: Gagal baca HX711!")
        GPIO.cleanup()
        return
    print(f" selesai. Raw benda = {benda_raw:.0f}")

    # ── Hitung faktor ──
    # Formula: (raw_benda - raw_tare) = gram * CALIBRATION_FACTOR
    # Jadi:    CALIBRATION_FACTOR = (raw_benda - raw_tare) / gram
    delta = benda_raw - tare_raw
    if abs(delta) < 100:
        print("\nERROR: Perbedaan raw terlalu kecil. Periksa wiring load cell!")
        GPIO.cleanup()
        return

    cal_factor = delta / berat_acuan_gram

    print("\n" + "=" * 50)
    print(f"  Raw Tare           : {tare_raw:.0f}")
    print(f"  Raw Benda Acuan    : {benda_raw:.0f}")
    print(f"  Delta Raw          : {delta:.0f}")
    print(f"  Berat Acuan        : {berat_acuan_gram} gram")
    print(f"\n  *** CALIBRATION_FACTOR = {cal_factor:.4f} ***")
    print("=" * 50)

    # ── Verifikasi ──
    print("\nVerifikasi: membaca berat benda acuan...")
    time.sleep(0.5)
    ver_raw = read_avg(hx, 10)
    if ver_raw is not None:
        berat_terbaca = (ver_raw - tare_raw) / cal_factor
        error_pct = abs(berat_terbaca - berat_acuan_gram) / berat_acuan_gram * 100
        print(f"  Berat terbaca : {berat_terbaca:.1f} gram")
        print(f"  Berat acuan   : {berat_acuan_gram:.1f} gram")
        print(f"  Error         : {error_pct:.1f}%")
        if error_pct < 2:
            print("  ✓ Akurasi BAIK (< 2% error)")
        elif error_pct < 5:
            print("  ~ Akurasi CUKUP (< 5% error)")
        else:
            print("  ✗ Error besar — ulangi kalibrasi dengan lebih banyak sampel")

    print(f"""
Langkah selanjutnya:
  Buka file timbangan.py, cari baris:
    CALIBRATION_FACTOR = 23.95
  Ganti dengan:
    CALIBRATION_FACTOR = {cal_factor:.4f}
""")

    GPIO.cleanup()
    hx.power_down()

if __name__ == "__main__":
    main()
