#!/usr/bin/env python3
"""
calibrate.py — Mencari CALIBRATION_FACTOR untuk load cell Anda
================================================================

Faktor kalibrasi bersifat SPESIFIK PER PERANGKAT. Nilai bawaan repositori ini
(24.1850) berasal dari unit referensi Tugas Akhir; load cell, mekanik dudukan,
dan modul HX711 yang berbeda akan menghasilkan angka yang berbeda pula.

Cara pakai:

    cd device
    python3 calibrate.py

Siapkan sebuah beban acuan yang massanya sudah diketahui pasti — misalnya
anak timbangan, atau air kemasan bersegel yang tertera beratnya. Semakin
mendekati kisaran kerja timbangan, semakin baik hasilnya.

Metode pengambilan sampel di sini sengaja dibuat identik dengan main.py
(trimmed mean lalu median) agar faktor yang dihasilkan konsisten dengan
pembacaan saat sistem berjalan.
"""

import os
import statistics
import sys
import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("[ERROR] RPi.GPIO tidak ditemukan. Jalankan skrip ini di Raspberry Pi.")
    sys.exit(1)

try:
    from hx711 import HX711
except ImportError:
    print("[ERROR] Modul hx711 tidak ditemukan.  pip install hx711")
    sys.exit(1)


# ── Konfigurasi (samakan dengan .env / main.py) ──────────────────────────────
def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

HX_DOUT = int(os.getenv("HX_DOUT", 17))
HX_SCK = int(os.getenv("HX_SCK", 27))

SAMPLES_PER_READ = 15    # lebih banyak dari runtime — kalibrasi butuh presisi
TRIM_RATIO = 0.20
SETTLE_SECONDS = 3


def _read_raw_samples(hx, n):
    """Ambil n sampel mentah, buang yang gagal."""
    out = []
    for _ in range(n):
        try:
            val = hx.get_raw_data(times=1)
            if isinstance(val, list):
                val = val[0] if val else None
            if val is not None:
                out.append(float(val))
        except Exception:
            pass
        time.sleep(0.01)
    return out


def _trim_core(values, ratio):
    """Buang nilai ekstrem di kedua ujung — meredam spike EMI."""
    if len(values) < 3:
        return values
    values = sorted(values)
    k = max(1, int(len(values) * ratio))
    core = values[k:-k]
    return core if core else values


def _stable_raw(hx, label):
    """Baca beberapa siklus lalu ambil mediannya."""
    print(f"  Membaca {label}", end="", flush=True)
    readings = []
    for _ in range(5):
        raws = _read_raw_samples(hx, SAMPLES_PER_READ)
        if len(raws) >= 3:
            readings.append(statistics.median(_trim_core(raws, TRIM_RATIO)))
        print(".", end="", flush=True)
    print()
    if not readings:
        print("\n[ERROR] Tidak ada pembacaan valid. Periksa kabel HX711.")
        sys.exit(1)
    spread = max(readings) - min(readings)
    return statistics.median(readings), spread


def main():
    print("=" * 62)
    print("  KALIBRASI LOAD CELL — Timbangan IoT")
    print("=" * 62)
    print(f"  Pin HX711 : DOUT=GPIO{HX_DOUT}  SCK=GPIO{HX_SCK}")
    print()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    hx = HX711(dout_pin=HX_DOUT, pd_sck_pin=HX_SCK)

    try:
        # ── Langkah 1: nol ───────────────────────────────────────────────
        print("LANGKAH 1 — Kosongkan platform timbangan sepenuhnya.")
        input("           Tekan ENTER bila sudah kosong... ")
        print(f"  Menunggu {SETTLE_SECONDS} detik agar pembacaan tenang...")
        time.sleep(SETTLE_SECONDS)

        tare_val, tare_spread = _stable_raw(hx, "titik nol")
        print(f"  Nilai nol (tare) : {tare_val:.1f}")
        print(f"  Sebaran          : {tare_spread:.1f}")
        if tare_spread > 5000:
            print("  ⚠️  Sebaran cukup besar — periksa kabel, hindari EMI,")
            print("      dan pastikan platform tidak bergetar.")
        print()

        # ── Langkah 2: beban acuan ───────────────────────────────────────
        print("LANGKAH 2 — Letakkan beban acuan yang Anda ketahui massanya.")
        raw_input_str = input("           Berat beban dalam GRAM (mis. 1000): ").strip()
        try:
            known_g = float(raw_input_str.replace(",", "."))
        except ValueError:
            print("[ERROR] Masukan bukan angka.")
            return 1
        if known_g <= 0:
            print("[ERROR] Berat harus lebih besar dari nol.")
            return 1
        if known_g < 100:
            print("  ⚠️  Beban di bawah 100 g memberi hasil kurang stabil.")

        input("           Tekan ENTER bila beban sudah di atas platform... ")
        print(f"  Menunggu {SETTLE_SECONDS} detik agar pembacaan tenang...")
        time.sleep(SETTLE_SECONDS)

        load_val, load_spread = _stable_raw(hx, "beban acuan")
        print(f"  Nilai berbeban   : {load_val:.1f}")
        print(f"  Sebaran          : {load_spread:.1f}")
        print()

        # ── Hitung ───────────────────────────────────────────────────────
        delta = load_val - tare_val
        if abs(delta) < 1000:
            print("[ERROR] Selisih pembacaan terlalu kecil.")
            print("        Kemungkinan penyebab: beban belum menyentuh platform,")
            print("        kabel load cell longgar, atau modul HX711 rusak.")
            return 1

        factor = delta / known_g

        print("=" * 62)
        print(f"  CALIBRATION_FACTOR = {factor:.4f}")
        print("=" * 62)
        print()
        print("  Salin nilai tersebut ke device/.env :")
        print()
        print(f"      CALIBRATION_FACTOR={factor:.4f}")
        print()

        if factor < 0:
            print("  ⚠️  Faktor bernilai negatif. Ini berarti polaritas load cell")
            print("      terbalik. Boleh dipakai apa adanya, atau tukar kabel")
            print("      E+/E- (atau A+/A-) lalu kalibrasi ulang.")
            print()

        # ── Verifikasi ───────────────────────────────────────────────────
        jawab = input("Uji hasil kalibrasi sekarang? [Y/n] ").strip().lower()
        if jawab in ("", "y", "ya", "yes"):
            print()
            print("Letakkan beban apa pun. Tekan CTRL+C untuk berhenti.")
            print()
            try:
                while True:
                    raws = _read_raw_samples(hx, SAMPLES_PER_READ)
                    if len(raws) >= 3:
                        med = statistics.median(_trim_core(raws, TRIM_RATIO))
                        grams = (med - tare_val) / factor
                        bar = "█" * min(40, max(0, int(abs(grams) / 50)))
                        print(f"\r  {grams / 1000:7.3f} kg  {bar:<40}", end="", flush=True)
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("\n\nSelesai.")

        return 0

    except KeyboardInterrupt:
        print("\n\nKalibrasi dibatalkan.")
        return 130
    finally:
        try:
            hx.power_down()
        except Exception:
            pass
        GPIO.cleanup()


if __name__ == "__main__":
    sys.exit(main())
