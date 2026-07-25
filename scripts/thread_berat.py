#!/usr/bin/env python3
"""
scripts/thread_berat.py — Thread pembacaan berat (HX711 + filter Stable Lock).

TANPA IoT: modul ini murni membaca load cell dan menulis hasilnya ke shared
state. Tidak ada request jaringan, tidak ada akses LCD, tidak ada kamera.

Alur filter:
    sampel mentah → trimmed median → gerbang kestabilan (opsional) →
    deadband nol → rolling median → konfirmasi lompatan → STABLE LOCK

Uji mandiri (di Raspberry Pi):
    python3 scripts/thread_berat.py
"""

import os
import sys
import time
import statistics
import collections
from typing import Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.common import (
    # konfigurasi
    HX_DOUT, HX_SCK, CALIBRATION_FACTOR, NOISE_THRESHOLD_KG, TARE_SAMPLES,
    INTERVAL_BERAT, AUTOTARE_IDLE_SEC, AUTOTARE_ZERO_KG,
    RAW_SAMPLES_PER_READ, RAW_SAMPLE_DELAY, TRIM_RATIO,
    STABILITY_GATE_ENABLED, STABILITY_MULTIPLIER,
    STABILITY_MIN_SPREAD_G, STABILITY_MAX_SPREAD_G,
    MEDIAN_WINDOW, SPIKE_DELTA_KG, SPIKE_CONFIRM_COUNT, DEADBAND_KG,
    DIAG_LOG_INTERVAL,
    LOCK_ENABLED, LOCK_TOLERANCE_KG, LOCK_STABLE_CYCLES,
    LOCK_RELEASE_DELTA_KG, LOCK_RELEASE_ZERO_KG,
    # runtime
    log, set_state, is_running, stop_event, berat_ready,
)

from hx711 import HX711


# ═══════════════════════════════════════════════════════════════════════════════
#  PEMBACAAN MENTAH & TARE
# ═══════════════════════════════════════════════════════════════════════════════
def _hx711_read_raw_samples(hx: HX711, n: int) -> list:
    """Ambil n sampel raw MENTAH dari HX711 (belum difilter)."""
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        if raw is not False and raw is not None:
            vals.append(raw)
        if RAW_SAMPLE_DELAY > 0:
            time.sleep(RAW_SAMPLE_DELAY)
    return vals


def _trim_core(values: list, trim_ratio: float) -> list:
    """Buang trim_ratio bagian ter-tinggi & ter-rendah, sisakan sampel inti."""
    if not values:
        return []
    s = sorted(values)
    k = int(len(s) * trim_ratio)
    if (len(s) - 2 * k) >= 1 and k > 0:
        return s[k:len(s) - k]
    return s


def _hx711_tare(hx: HX711) -> float:
    """Nilai tare (offset) memakai trimmed median agar tahan outlier."""
    log(f"Tare: mengambil {TARE_SAMPLES} sampel...")
    raws = _hx711_read_raw_samples(hx, TARE_SAMPLES)
    core = _trim_core(raws, TRIM_RATIO)
    tare = statistics.median(core) if core else 0.0
    log(f"Tare offset = {tare:.1f}")
    return tare


def _measure_noise_baseline(hx: HX711, tare_val: float, rounds: int = 5) -> float:
    """Ukur noise baseline (spread rata-rata tanpa beban) untuk gerbang adaptif."""
    log(f"Mengukur noise baseline ({rounds} ronde)...")
    spreads = []
    for i in range(rounds):
        raws = _hx711_read_raw_samples(hx, RAW_SAMPLES_PER_READ)
        if len(raws) < 3:
            continue
        core  = _trim_core(raws, TRIM_RATIO)
        grams = [(r - tare_val) / CALIBRATION_FACTOR for r in core]
        if grams:
            spread = max(grams) - min(grams)
            spreads.append(spread)
            log(f"  Ronde {i+1}: spread = {spread:.1f} g")

    if spreads:
        baseline = statistics.median(spreads)
    else:
        baseline = STABILITY_MAX_SPREAD_G / STABILITY_MULTIPLIER
        log("  ⚠ Tidak ada data spread — pakai fallback.", "WARN")

    threshold = max(baseline * STABILITY_MULTIPLIER, STABILITY_MIN_SPREAD_G)
    threshold = min(threshold, STABILITY_MAX_SPREAD_G)
    log(f"Noise baseline = {baseline:.1f} g → ambang kestabilan = {threshold:.1f} g")
    return threshold


def _read_grams_and_spread(
    hx: HX711, tare_val: float
) -> Tuple[Optional[float], Optional[float]]:
    """Baca satu siklus → (gram_median, spread_gram). (None, None) bila gagal."""
    raws = _hx711_read_raw_samples(hx, RAW_SAMPLES_PER_READ)
    if len(raws) < 3:
        return None, None

    core  = _trim_core(raws, TRIM_RATIO)
    grams = [(r - tare_val) / CALIBRATION_FACTOR for r in core]
    if not grams:
        return None, None

    return statistics.median(grams), max(grams) - min(grams)


# ═══════════════════════════════════════════════════════════════════════════════
#  FILTER BERAT + STABLE LOCK
# ═══════════════════════════════════════════════════════════════════════════════
class WeightFilter:
    """
    Filter berat dengan stable lock — seperti timbangan digital komersial.
    Alur: gerbang kestabilan (opsional) → deadband nol → rolling median →
          konfirmasi lompatan → stable lock (kunci tampilan setelah stabil).
    """

    def __init__(self, stability_threshold_g: float):
        self._buf              = collections.deque(maxlen=MEDIAN_WINDOW)
        self._stable_kg        = 0.0
        self._pending_kg       = None
        self._pending_n        = 0
        self._stability_thresh = stability_threshold_g
        self._blocked_count    = 0

        # Stable lock state
        self._locked       = False
        self._lock_value   = 0.0
        self._lock_history = collections.deque(maxlen=LOCK_STABLE_CYCLES)

    def reset(self, new_threshold_g: Optional[float] = None):
        self._buf.clear()
        self._stable_kg     = 0.0
        self._pending_kg    = None
        self._pending_n     = 0
        self._blocked_count = 0
        self._locked        = False
        self._lock_value    = 0.0
        self._lock_history.clear()
        if new_threshold_g is not None:
            self._stability_thresh = new_threshold_g

    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    def _unlock(self, reason: str = ""):
        if self._locked:
            log(f"Lock LEPAS — {reason} (was {self._lock_value:.2f} kg)")
        self._locked     = False
        self._lock_value = 0.0
        self._lock_history.clear()

    def update(self, gram_med: Optional[float], spread_g: Optional[float]) -> float:
        # Gagal baca → pertahankan nilai terakhir.
        if gram_med is None:
            return self._lock_value if self._locked else self._stable_kg

        # (1) Gerbang kestabilan — OPSIONAL.
        if STABILITY_GATE_ENABLED:
            if spread_g is not None and spread_g > self._stability_thresh:
                self._blocked_count += 1
                return self._lock_value if self._locked else self._stable_kg

        kg = gram_med / 1000.0

        # (2) Deadband nol.
        if abs(kg) < NOISE_THRESHOLD_KG:
            kg = 0.0

        # (3) Rolling median.
        self._buf.append(kg)
        kg_med = statistics.median(self._buf)

        # ── Jika TERKUNCI: cek apakah perlu lepas kunci ──
        if self._locked:
            delta = abs(kg_med - self._lock_value)
            if kg_med < LOCK_RELEASE_ZERO_KG:
                self._unlock("barang diangkat")
                self._stable_kg = 0.0
                self._buf.clear()
                return 0.0
            if delta > LOCK_RELEASE_DELTA_KG:
                self._unlock(f"delta {delta:.2f} kg")
                self._stable_kg = kg_med
                return self._stable_kg
            return self._lock_value

        # ── TIDAK terkunci: filter normal ──

        # (4) Konfirmasi lompatan besar.
        if abs(kg_med - self._stable_kg) >= SPIKE_DELTA_KG:
            if (self._pending_kg is not None
                    and abs(kg_med - self._pending_kg) < SPIKE_DELTA_KG):
                self._pending_n += 1
            else:
                self._pending_kg = kg_med
                self._pending_n  = 1

            if self._pending_n >= SPIKE_CONFIRM_COUNT:
                self._stable_kg  = kg_med
                self._pending_kg = None
                self._pending_n  = 0
        else:
            self._stable_kg  = kg_med
            self._pending_kg = None
            self._pending_n  = 0

        # Deadband akhir.
        if abs(self._stable_kg) < DEADBAND_KG:
            self._stable_kg = 0.0

        # (5) Stable lock — cek apakah pembacaan sudah stabil.
        if LOCK_ENABLED and self._stable_kg > LOCK_RELEASE_ZERO_KG:
            self._lock_history.append(self._stable_kg)
            if len(self._lock_history) >= LOCK_STABLE_CYCLES:
                r_min = min(self._lock_history)
                r_max = max(self._lock_history)
                if (r_max - r_min) <= LOCK_TOLERANCE_KG:
                    self._lock_value = round(statistics.median(self._lock_history), 2)
                    self._locked = True
                    log(f"Lock AKTIF — {self._lock_value:.2f} kg "
                        f"(range {r_max - r_min:.3f})")
        else:
            self._lock_history.clear()

        return self._lock_value if self._locked else self._stable_kg


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT THREAD
# ═══════════════════════════════════════════════════════════════════════════════
def thread_berat():
    """Thread pembacaan HX711 kontinu (filter anti-noise + stable lock)."""
    log("Thread Berat: mulai inisialisasi HX711...")
    hx = HX711(HX_DOUT, HX_SCK)
    tare_val = _hx711_tare(hx)

    if STABILITY_GATE_ENABLED:
        stability_thresh = _measure_noise_baseline(hx, tare_val)
        log(f"Gerbang kestabilan AKTIF, ambang={stability_thresh:.1f}g.")
    else:
        stability_thresh = STABILITY_MAX_SPREAD_G
        log("Gerbang kestabilan NONAKTIF — mengandalkan rolling median.")

    filt = WeightFilter(stability_thresh)
    log("Thread Berat: siap.")
    berat_ready.set()   # tare selesai → komponen berat siap

    last_nonzero_time = time.time()
    cycle_count = 0

    try:
        while is_running():
            gram_med, spread_g = _read_grams_and_spread(hx, tare_val)
            berat = filt.update(gram_med, spread_g)
            set_state("berat_kg", berat)
            set_state("locked", filt.is_locked)

            cycle_count += 1
            if DIAG_LOG_INTERVAL > 0 and cycle_count % DIAG_LOG_INTERVAL == 0:
                spread_str = f"{spread_g:.1f}" if spread_g is not None else "N/A"
                gram_str   = f"{gram_med:.1f}" if gram_med is not None else "N/A"
                lock_str   = "LOCKED" if filt.is_locked else "---"
                log(
                    f"[DIAG] siklus={cycle_count} | raw={gram_str}g | "
                    f"spread={spread_str}g | tampil={berat:.2f}kg | {lock_str}",
                    "DEBUG",
                )

            # ── Auto-tare saat idle lama (koreksi drift) ──
            if berat > AUTOTARE_ZERO_KG:
                last_nonzero_time = time.time()
            else:
                idle_duration = time.time() - last_nonzero_time
                if idle_duration >= AUTOTARE_IDLE_SEC:
                    log(
                        f"Auto-tare: idle {idle_duration:.0f}s ≥ "
                        f"{AUTOTARE_IDLE_SEC:.0f}s — tare ulang untuk koreksi drift...",
                        "INFO",
                    )
                    tare_val = _hx711_tare(hx)
                    if STABILITY_GATE_ENABLED:
                        stability_thresh = _measure_noise_baseline(hx, tare_val)
                    filt.reset(new_threshold_g=stability_thresh)
                    set_state("berat_kg", 0.0)
                    last_nonzero_time = time.time()
                    cycle_count = 0

            stop_event.wait(timeout=INTERVAL_BERAT)

    except Exception as e:
        log(f"Thread Berat error tak terduga: {e}", "ERROR")
    finally:
        try:
            hx.power_down()
            log("HX711 dimatikan.")
        except Exception:
            pass
        log("Thread Berat: berhenti.")


# ═══════════════════════════════════════════════════════════════════════════════
#  UJI MANDIRI — python3 scripts/thread_berat.py
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import threading
    import RPi.GPIO as GPIO
    from scripts.common import get_state, request_stop

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    t = threading.Thread(target=thread_berat, name="Thread-Berat", daemon=True)
    t.start()
    print("Uji mandiri berat. CTRL+C untuk keluar.")

    try:
        while True:
            time.sleep(0.5)
            lock = "LOCKED" if get_state("locked") else "      "
            print(f"\rBerat: {get_state('berat_kg'):6.2f} kg  {lock}", end="")
    except KeyboardInterrupt:
        print()
    finally:
        request_stop()
        t.join(timeout=3.0)
        GPIO.cleanup()
