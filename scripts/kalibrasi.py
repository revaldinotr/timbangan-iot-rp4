# Program Kalibrasi Load Cell HX711
# File: kalibrasi.py

import time
import statistics
import RPi.GPIO as GPIO
from hx711 import HX711

HX_DOUT = 17
HX_SCK  = 27

def baca_rata(hx, n):
    """Median dari n pembacaan raw HX711."""
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        if raw is not False and raw is not None:
            vals.append(raw)
        time.sleep(0.05)
    return statistics.median(vals) if vals else None

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    hx = HX711(HX_DOUT, HX_SCK)

    print("=== KALIBRASI LOAD CELL HX711 ===")

    # 1. Tare (load cell kosong)
    input("\nPastikan load cell KOSONG. Tekan ENTER...")
    tare_raw = baca_rata(hx, 20)
    print(f"Raw tare = {tare_raw:.0f}")

    # 2. Baca dengan beban acuan
    print("\nLetakkan benda dengan berat DIKETAHUI.")
    berat_acuan = float(input("Berat benda acuan (gram): "))
    input("Tekan ENTER untuk membaca...")
    benda_raw = baca_rata(hx, 20)
    print(f"Raw benda = {benda_raw:.0f}")

    # 3. Hitung faktor kalibrasi
    delta = benda_raw - tare_raw
    cal_factor = delta / berat_acuan

    print("\n=== HASIL ===")
    print(f"Delta Raw          : {delta:.0f}")
    print(f"Berat Acuan        : {berat_acuan:.0f} gram")
    print(f"CALIBRATION_FACTOR = {cal_factor:.4f}")

    # 4. Verifikasi
    ver_raw = baca_rata(hx, 10)
    berat_terbaca = (ver_raw - tare_raw) / cal_factor
    error = abs(berat_terbaca - berat_acuan) / berat_acuan * 100
    print(f"\nBerat terbaca : {berat_terbaca:.1f} gram")
    print(f"Error         : {error:.1f}%")

    hx.power_down()
    GPIO.cleanup()

if __name__ == "__main__":
    main()
