# Lampiran 3. Program Pengambilan Data Uji Sistem
# File: tb-test.py

import time
import statistics
import collections
import RPi.GPIO as GPIO
from hx711 import HX711


# ---------- KONFIGURASI ----------
HX_DOUT            = 17
HX_SCK             = 27
CALIBRATION_FACTOR = 24.1850
NOISE_THRESHOLD_KG = 0.02
TARE_SAMPLES       = 15

RAW_SAMPLES_PER_READ = 5
TRIM_RATIO           = 0.20
MEDIAN_WINDOW        = 3
DEADBAND_KG          = 0.05

LOCK_TOLERANCE_KG     = 0.20
LOCK_STABLE_CYCLES    = 4
LOCK_RELEASE_DELTA_KG = 1.0
LOCK_RELEASE_ZERO_KG  = 0.15


# ---------- PEMBACAAN SENSOR ----------
def _baca_sampel(hx, n):
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        if raw is not False and raw is not None:
            vals.append(raw)
    return vals

def _trim(values, ratio):
    if not values:
        return []
    s = sorted(values)
    k = int(len(s) * ratio)
    if (len(s) - 2 * k) >= 1 and k > 0:
        return s[k:len(s) - k]
    return s

def hx711_tare(hx):
    print(f"Tare: mengambil {TARE_SAMPLES} sampel...")
    raws = _baca_sampel(hx, TARE_SAMPLES)
    core = _trim(raws, TRIM_RATIO)
    tare = statistics.median(core) if core else 0.0
    print(f"Tare offset = {tare:.1f}")
    return tare

def baca_gram(hx, tare):
    raws = _baca_sampel(hx, RAW_SAMPLES_PER_READ)
    if len(raws) < 3:
        return None
    core  = _trim(raws, TRIM_RATIO)
    grams = [(r - tare) / CALIBRATION_FACTOR for r in core]
    return statistics.median(grams) if grams else None


# ---------- FILTER BERAT (sama dengan program utama) ----------
class WeightFilter:
    def __init__(self):
        self._buf          = collections.deque(maxlen=MEDIAN_WINDOW)
        self._stable_kg    = 0.0
        self._locked       = False
        self._lock_value   = 0.0
        self._lock_history = collections.deque(maxlen=LOCK_STABLE_CYCLES)

    @property
    def is_locked(self):
        return self._locked

    def update(self, gram):
        if gram is None:
            return self._lock_value if self._locked else self._stable_kg

        kg = gram / 1000.0
        if abs(kg) < NOISE_THRESHOLD_KG:
            kg = 0.0

        self._buf.append(kg)
        kg_med = statistics.median(self._buf)

        if self._locked:
            if kg_med < LOCK_RELEASE_ZERO_KG:
                self._locked = False
                self._lock_value = 0.0
                self._stable_kg = 0.0
                self._buf.clear()
                self._lock_history.clear()
                return 0.0
            if abs(kg_med - self._lock_value) > LOCK_RELEASE_DELTA_KG:
                self._locked = False
                self._lock_value = 0.0
                self._lock_history.clear()
                self._stable_kg = kg_med
                return self._stable_kg
            return self._lock_value

        self._stable_kg = kg_med
        if abs(self._stable_kg) < DEADBAND_KG:
            self._stable_kg = 0.0

        if self._stable_kg > LOCK_RELEASE_ZERO_KG:
            self._lock_history.append(self._stable_kg)
            if len(self._lock_history) >= LOCK_STABLE_CYCLES:
                rentang = max(self._lock_history) - min(self._lock_history)
                if rentang <= LOCK_TOLERANCE_KG:
                    self._lock_value = round(statistics.median(self._lock_history), 2)
                    self._locked = True
        else:
            self._lock_history.clear()

        return self._lock_value if self._locked else self._stable_kg


# ---------- FUNGSI BANTU PENGUJIAN ----------
def baca_stabil(hx, tare, timeout=30):
    """Baca sampai nilai terkunci. Kembalikan kg atau None."""
    filt = WeightFilter()
    t0 = time.time()
    while time.time() - t0 < timeout:
        gram = baca_gram(hx, tare)
        b = filt.update(gram)
        if filt.is_locked and b > NOISE_THRESHOLD_KG:
            return b
        time.sleep(0.02)
    b = filt._stable_kg
    return b if b > NOISE_THRESHOLD_KG else None


def tunggu_kosong(hx, tare, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        gram = baca_gram(hx, tare)
        if gram is not None and abs(gram / 1000.0) < LOCK_RELEASE_ZERO_KG:
            return True
        time.sleep(0.02)
    return False


def hitung_statistik(data, ref_kg):
    n = len(data)
    mean = statistics.mean(data)
    std = statistics.stdev(data) if n > 1 else 0.0
    rsd = (std / mean * 100) if mean > 0 else 0.0
    err_pct = (abs(mean - ref_kg) / ref_kg * 100) if ref_kg > 0 else 0.0
    return {
        "n": n, "mean": mean, "std": std, "rsd": rsd,
        "min": min(data), "max": max(data), "range": max(data) - min(data),
        "err_pct": err_pct, "akurasi": 100 - err_pct,
    }


# ---------- 1. UJI AKURASI & PRESISI ----------
def uji_akurasi_presisi(hx):
    print("\n-- UJI AKURASI & PRESISI --")
    beban_str = input("Beban referensi (kg), pisah koma:\n  > ").strip()
    try:
        beban_list = [float(b.strip()) for b in beban_str.split(",")]
    except ValueError:
        print("Format salah!")
        return

    n_rep = int(input("Pengulangan per beban: ") or "5")
    print(f"\n{len(beban_list)} variasi x {n_rep} pengulangan")
    input("Pastikan load cell KOSONG, tekan Enter...")

    tv = hx711_tare(hx)
    time.sleep(1)

    semua = {}
    for ib, ref in enumerate(beban_list):
        print(f"\n=== BEBAN {ib+1}/{len(beban_list)}: {ref:.2f} kg ===")
        data = []

        for rep in range(1, n_rep + 1):
            print(f"  [{rep}/{n_rep}] Taruh beban {ref:.2f} kg ...")
            nilai = baca_stabil(hx, tv, timeout=30)
            if nilai is not None:
                err = abs(nilai - ref) / ref * 100 if ref > 0 else 0
                data.append(nilai)
                print(f"  [{rep}/{n_rep}] OK  {nilai:.2f} kg (error: {err:.2f}%)")
            else:
                print(f"  [{rep}/{n_rep}] TIMEOUT!")

            if rep < n_rep:
                print("  Angkat beban ...")
                tunggu_kosong(hx, tv)
                time.sleep(1)

        if data:
            s = hitung_statistik(data, ref)
            semua[ref] = s
            print(f"  HASIL: Mean={s['mean']:.2f}  Std={s['std']:.4f}  RSD={s['rsd']:.2f}%")
            print(f"         Error={s['err_pct']:.2f}%  Akurasi={s['akurasi']:.2f}%")

        if ib < len(beban_list) - 1:
            print(f"\n  Siapkan beban berikutnya ({beban_list[ib + 1]:.2f} kg) ...")
            tunggu_kosong(hx, tv, timeout=30)
            time.sleep(2)

    # Tabel ringkasan
    print("\n=== RINGKASAN -- Akurasi & Presisi ===")
    print(f"  {'Ref(kg)':<9} {'Mean':<9} {'Err%':<8} {'Std':<9} {'RSD%':<8} {'Akurasi%':<9}")
    for ref, s in semua.items():
        print(f"  {ref:<9.2f} {s['mean']:<9.2f} {s['err_pct']:<8.2f} "
              f"{s['std']:<9.4f} {s['rsd']:<8.2f} {s['akurasi']:<9.2f}")


# ---------- 2. UJI STABILITAS ----------
def uji_stabilitas(hx):
    print("\n-- UJI STABILITAS --")
    ref = float(input("Beban referensi (kg): ") or "10")
    durasi = int(input("Durasi (menit) [5]: ") or "5")
    interval = int(input("Interval pembacaan (detik) [30]: ") or "30")
    n_read = (durasi * 60) // interval

    print(f"\n{n_read} pembacaan selama {durasi} mnt (tiap {interval}s)")
    input("ANGKAT beban dulu untuk tare, tekan Enter...")
    tv = hx711_tare(hx)
    time.sleep(1)
    input(f"TARUH beban {ref:.2f} kg, tekan Enter untuk mulai...")

    data = []
    t0 = time.time()
    for i in range(1, n_read + 1):
        el = time.time() - t0
        m, d = int(el // 60), int(el % 60)

        nilai = baca_stabil(hx, tv, timeout=30)
        if nilai is not None:
            data.append(nilai)
            drift = nilai - data[0] if len(data) > 1 else 0.0
            err = abs(nilai - ref) / ref * 100 if ref > 0 else 0
            print(f"  [{m:02d}:{d:02d}] #{i}: {nilai:.2f} kg  drift:{drift:+.3f}  err:{err:.2f}%")
        else:
            print(f"  [{m:02d}:{d:02d}] #{i}: TIMEOUT")

        if i < n_read:
            wait_until = t0 + (i * interval)
            rem = wait_until - time.time()
            if rem > 0:
                time.sleep(rem)

    if len(data) >= 2:
        s = hitung_statistik(data, ref)
        td = data[-1] - data[0]
        md = max(data) - min(data)
        print("\n=== HASIL UJI STABILITAS ===")
        print(f"  Referensi   : {ref:.2f} kg")
        print(f"  Durasi      : {durasi} mnt ({len(data)} pembacaan)")
        print(f"  Mean        : {s['mean']:.4f} kg")
        print(f"  Std deviasi : {s['std']:.4f} kg")
        print(f"  RSD         : {s['rsd']:.4f}%")
        print(f"  Drift total : {td:+.4f} kg")
        print(f"  Drift maks  : {md:.4f} kg")
        print(f"  Akurasi     : {s['akurasi']:.2f}%")


# ---------- PROGRAM UTAMA ----------
def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    hx = HX711(HX_DOUT, HX_SCK)

    hx711_tare(hx)  # tare awal untuk memastikan sensor siap

    print("\n=== MODE PENGUJIAN TIMBANGAN ===")
    print("  1. Uji Akurasi & Presisi")
    print("  2. Uji Stabilitas")
    print("  0. Keluar")
    pilihan = input("Pilih [1/2/0]: ").strip()

    try:
        if pilihan == "1":
            uji_akurasi_presisi(hx)
        elif pilihan == "2":
            uji_stabilitas(hx)
        else:
            print("Keluar.")
    except KeyboardInterrupt:
        print("\nPengujian dibatalkan.")
    finally:
        hx.power_down()
        GPIO.cleanup()
        print("Mode pengujian selesai.")


if __name__ == "__main__":
    main()
