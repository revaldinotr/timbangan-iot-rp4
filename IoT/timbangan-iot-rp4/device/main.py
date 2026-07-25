#!/usr/bin/env python3
import os
import sys
import time
import base64
import threading
import queue
import statistics
import collections
import requests

from collections import deque
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import cv2


# ═══════════════════════════════════════════════════════════════════════════════
#  KONFIGURASI
#  Nilai rahasia & spesifik-perangkat dibaca dari berkas .env (lihat .env.example).
#  TIDAK ADA kredensial yang di-hardcode di berkas ini — aman untuk di-commit.
# ═══════════════════════════════════════════════════════════════════════════════

# Root direktori = lokasi file ini (untuk folder model/, captures/, logs/).
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    """Pembaca .env minimal — tanpa dependensi tambahan.

    Variabel yang sudah ada di lingkungan TIDAK ditimpa, sehingga
    `GAS_SCRIPT_ID=xxx python3 main.py` tetap bisa dipakai untuk override.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv(os.path.join(_ROOT_DIR, ".env"))


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        print(f"[WARN] {key} bukan angka valid, memakai default {default}")
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        print(f"[WARN] {key} bukan angka valid, memakai default {default}")
        return default


# ── Google Apps Script ──
# Deployment ID dari URL: script.google.com/macros/s/<DEPLOYMENT_ID>/exec
#
# ⚠️  PERLAKUKAN SEBAGAI RAHASIA. Endpoint /exec yang di-deploy dengan akses
#     "Anyone" adalah endpoint tulis TANPA autentikasi: siapa pun yang memegang
#     URL-nya bisa menyisipkan baris ke Spreadsheet dan mengunggah berkas ke
#     Google Drive Anda. Simpan hanya di .env, jangan pernah di-commit.
GOOGLE_SHEETS_SCRIPT_ID = os.getenv("GAS_SCRIPT_ID", "").strip()

if not GOOGLE_SHEETS_SCRIPT_ID:
    print(
        "[ERROR] GAS_SCRIPT_ID belum diatur.\n"
        "        Salin device/.env.example menjadi device/.env, lalu isi\n"
        "        GAS_SCRIPT_ID dengan Deployment ID Apps Script Anda.\n"
        "        Panduan: docs/SETUP.md bagian 'Deploy Apps Script'."
    )
    sys.exit(1)

GOOGLE_SHEETS_URL        = f"https://script.google.com/macros/s/{GOOGLE_SHEETS_SCRIPT_ID}/exec"
GOOGLE_DRIVE_FOLDER_NAME = os.getenv("GAS_DRIVE_FOLDER", "Captures Data Sayur")

# Token bersama (opsional tapi SANGAT disarankan). Bila diisi, nilainya harus
# sama persis dengan SHARED_TOKEN di apps-script/pb_to_sheets.gs. Tanpa ini,
# endpoint /exec bisa ditulisi siapa pun yang mengetahui URL-nya.
GAS_SHARED_TOKEN = os.getenv("GAS_SHARED_TOKEN", "").strip()

if not GAS_SHARED_TOKEN:
    print(
        "[WARN] GAS_SHARED_TOKEN kosong — endpoint Apps Script berjalan TANPA "
        "autentikasi.\n"
        "       Siapa pun yang tahu URL /exec dapat menulis ke Spreadsheet dan "
        "Drive Anda.\n"
        "       Lihat docs/SECURITY-NOTES.md untuk cara mengaktifkannya."
    )

# ── Hardware: GPIO & HX711 (load cell) ──
HX_DOUT            = _env_int("HX_DOUT", 17)   # GPIO pin DOUT HX711
HX_SCK             = _env_int("HX_SCK", 27)    # GPIO pin SCK HX711

# Faktor kalibrasi BERSIFAT SPESIFIK PER PERANGKAT — bergantung load cell,
# mekanik dudukan, dan modul HX711 Anda. Nilai default di bawah adalah hasil
# kalibrasi unit referensi pada Tugas Akhir ini; unit Anda hampir pasti berbeda.
# Jalankan `python3 calibrate.py` untuk memperoleh nilai milik perangkat Anda.
CALIBRATION_FACTOR = _env_float("CALIBRATION_FACTOR", 24.1850)
NOISE_THRESHOLD_KG = 0.02     # Di bawah nilai ini dianggap nol / noise
TARE_SAMPLES       = 15       # Jumlah sampel untuk tare awal
INTERVAL_BERAT     = 0.05     # Interval antar siklus baca (detik)
AUTOTARE_IDLE_SEC  = 120.0    # Idle berapa detik sebelum auto-tare
AUTOTARE_ZERO_KG   = 0.05     # Batas "dianggap kosong" untuk memulai auto-tare

# ── Filter anti-noise (sentuhan konektor / EMI) ──
RAW_SAMPLES_PER_READ   = 5     # 5 sampel × ~100ms = ~0.5s per siklus
RAW_SAMPLE_DELAY       = 0.0
TRIM_RATIO             = 0.20  # Dari 5 sampel: buang 1 tertinggi + 1 terendah → sisa 3
STABILITY_GATE_ENABLED = False
STABILITY_MULTIPLIER   = 3.0
STABILITY_MIN_SPREAD_G = 20.0
STABILITY_MAX_SPREAD_G = 500.0
MEDIAN_WINDOW          = 3     # Rolling median kecil → respons cepat
SPIKE_DELTA_KG         = 999.0 # Konfirmasi spike DINONAKTIFKAN
SPIKE_CONFIRM_COUNT    = 1
DEADBAND_KG            = 0.05  # Histeresis di sekitar nol
DIAG_LOG_INTERVAL      = 10    # Log diagnostik setiap N siklus (0 = mati)

# ── Stable Lock (kunci nilai setelah stabil — seperti timbangan komersial) ──
LOCK_ENABLED           = True
LOCK_TOLERANCE_KG      = 0.20  # Pembacaan dalam ±200g dianggap stabil
LOCK_STABLE_CYCLES     = 4     # Harus stabil 4 siklus berturut (~2 detik)
LOCK_RELEASE_DELTA_KG  = 1.0   # Berat berubah ≥1kg → lepas kunci
LOCK_RELEASE_ZERO_KG   = 0.15  # Di bawah ini = barang diangkat → lepas kunci

# ── Hardware: LCD I2C 16x2 ──
LCD_ADDR = 0x27   # Alamat I2C LCD (cek: i2cdetect -y 1)
LCD_COLS = 16
LCD_ROWS = 2

# ── Splash / layar booting (tampil saat sistem menyiapkan model + tare) ──
SPLASH_SECONDS = 2.0   # Durasi tiap layar splash (detik)
# Tiap entri: (baris_atas, baris_bawah, center?)  — urutan: judul → Aryo → Reval
SPLASH_SCREENS = [
    ("Timbangan IoT", "Polsri 2026",   True),   # rata tengah
    ("Aryo",          "062330320613",  False),  # rata kiri (nama atas, NIM bawah)
    ("Reval",         "062330320631",  False),  # rata kiri
]

# ── Hardware: Push button ──
BTN_PIN     = 22   # GPIO pin tombol (aktif rendah, pull-up internal)
DEBOUNCE_MS = 300  # Software debounce tambahan (ms)

# ── Model YOLOv5 TFLite & kamera ──
# ⚠️  GANTI ke model FP32. FP32 = presisi penuh (bobot float32), biasanya sedikit
#     lebih akurat dari FP16 untuk objek kecil/jauh, tapi inferensi LEBIH LAMBAT
#     dan butuh RAM lebih besar di CM4. Lihat catatan performa di bawah file.
MODEL_PATH    = os.path.join(_ROOT_DIR, "model", "best-fp32.tflite")
CLASS_NAMES   = ["kentang", "tomat", "wortel"]
CLASS_COLORS  = {
    "kentang": (0, 200, 0),    # hijau
    "tomat"  : (0,  60, 255),  # merah
    "wortel" : (0, 165, 255),  # oranye
}
CONF_THRESH    = 0.08   # Confidence threshold deteksi objek
IOU_THRESH     = 0.15   # IOU threshold NMS
INPUT_SIZE     = 640    # Ukuran input model (px) — DITENTUKAN saat export, jangan ubah
NUM_THREADS    = 4      # Thread TFLite interpreter (CM4 = 4 core Cortex-A72)
WEBCAM_INDEX   = 0      # USB webcam → /dev/video0

# ── Resolusi CAPTURE kamera (DIPISAH dari ukuran input model) ──
# Webcam dibaca pada resolusi tinggi → di-letterbox ke INPUT_SIZE (640) di preprocess.
# Capture lebih tinggi memberi lebih banyak piksel pada objek JAUH sebelum di-resize,
# sehingga objek kecil/jauh lebih mungkin terdeteksi.
#   - 1280x720  : keseimbangan (disarankan untuk CM4 2GB)  ← default
#   - 1920x1080 : detail maksimal objek jauh, tapi CPU & RAM lebih berat
#   - 640x480   : ringan, tapi objek jauh sering terlewat (perilaku lama)
WEBCAM_WIDTH   = 1280
WEBCAM_HEIGHT  = 720
CONFIRM_FRAMES = 8      # Jumlah frame konsisten untuk konfirmasi jenis

# ── Penyimpanan lokal ──
CAPTURE_DIR = os.path.join(_ROOT_DIR, "captures")
LOG_DIR     = os.path.join(_ROOT_DIR, "logs")
JPEG_QUALITY = 70       # Kompresi foto capture (hemat upload base64)


# ── Import GPIO ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("[ERROR] RPi.GPIO tidak ditemukan! pip install RPi.GPIO")
    sys.exit(1)

# ── Import HX711 (load cell) ─────────────────────────────────────────────────
from hx711 import HX711

# ── Import LCD (RPLCD / CharLCD) ─────────────────────────────────────────────
try:
    from RPLCD.i2c import CharLCD
    RPLCD_AVAILABLE = True
except ImportError:
    CharLCD = None
    RPLCD_AVAILABLE = False
    print("[WARN] RPLCD tidak terinstall. LCD dinonaktifkan.")

# ── Import TFLite ────────────────────────────────────────────────────────────
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        import tensorflow as tf
        tflite = tf.lite
    except ImportError:
        print("[ERROR] tflite-runtime atau tensorflow tidak ditemukan!")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED STATE (thread-safe)
# ═══════════════════════════════════════════════════════════════════════════════
_lock  = threading.Lock()
_state = {
    "berat_kg"       : 0.0,    # berat tampil (nilai terkunci saat stabil)
    "locked"         : False,  # status kunci-stabil filter berat
    "jenis"          : "...",  # jenis terkonfirmasi saat ini
    "last_frame"     : None,   # frame BGR terakhir dari kamera
    "last_detections": [],     # deteksi terakhir [(x1,y1,x2,y2,name,conf), ...]
}

def get_state(key):
    with _lock:
        return _state[key]

def set_state(key, val):
    with _lock:
        _state[key] = val


# ─── Sinyal shutdown (lock-free, atomic) ──────────────────────────────────────
_stop_event = threading.Event()

def is_running() -> bool:
    return not _stop_event.is_set()

def should_stop() -> bool:
    return _stop_event.is_set()

def request_stop():
    _stop_event.set()


# ─── Sinyal "sistem siap" (untuk menahan splash sampai loading selesai) ────────
_berat_ready = threading.Event()   # di-set setelah tare HX711 selesai
_jenis_ready = threading.Event()   # di-set setelah model dimuat + kamera dibuka

def system_ready() -> bool:
    """True bila tare HX711 selesai DAN model+kamera siap."""
    return _berat_ready.is_set() and _jenis_ready.is_set()


# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGER
# ═══════════════════════════════════════════════════════════════════════════════
os.makedirs(LOG_DIR,     exist_ok=True)
os.makedirs(CAPTURE_DIR, exist_ok=True)
_log_lock = threading.Lock()

def log(msg: str, level: str = "INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    with _log_lock:
        print(line)
        try:
            logfile = os.path.join(LOG_DIR, f"main_{datetime.now().strftime('%Y%m%d')}.log")
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  LCD HELPER (RPLCD)
# ═══════════════════════════════════════════════════════════════════════════════
_lcd      = None
_lcd_lock = threading.Lock()

# Format item queue:
#   ("override", baris0, baris1, durasi_detik)  — tampilkan sementara
#   ("shutdown",)                                — tulis pesan akhir lalu keluar
_lcd_cmd_queue: queue.Queue = queue.Queue()

def lcd_init():
    global _lcd
    if not RPLCD_AVAILABLE:
        return
    try:
        _lcd = CharLCD(
            i2c_expander='PCF8574',
            address=LCD_ADDR,
            port=1,
            cols=LCD_COLS,
            rows=LCD_ROWS,
            charmap='A02',
            auto_linebreaks=True,
            backlight_enabled=True
        )
        with _lcd_lock:
            _lcd.clear()
            _lcd_write_unsafe(0, _center16(SPLASH_SCREENS[0][0]))
            _lcd_write_unsafe(1, _center16(SPLASH_SCREENS[0][1]))
        log(f"LCD I2C aktif @ 0x{LCD_ADDR:02X}")
    except Exception as e:
        log(f"LCD gagal: {e}", "WARN")
        _lcd = None

def _lcd_write_unsafe(row: int, text: str):
    """Tulis LCD TANPA lock — harus dipanggil di dalam blok `with _lcd_lock`."""
    if _lcd is None:
        return
    text = str(text).ljust(LCD_COLS)[:LCD_COLS]
    _lcd.cursor_pos = (row, 0)
    _lcd.write_string(text)

def _center16(text: str) -> str:
    """Rata-tengah teks dalam lebar LCD_COLS (16)."""
    return str(text)[:LCD_COLS].center(LCD_COLS)

def _lcd_show(line0: str, line1: str):
    """Tulis dua baris LCD dengan lock (dipakai fase splash)."""
    try:
        with _lcd_lock:
            _lcd_write_unsafe(0, line0)
            _lcd_write_unsafe(1, line1)
    except Exception as e:
        log(f"LCD splash error: {e}", "WARN")

def _run_splash():
    """
    Fase booting: tampilkan layar splash satu per satu (tiap SPLASH_SECONDS),
    lalu — bila model/tare BELUM siap — tahan di layar 'Menyiapkan...' (animasi
    titik) sampai system_ready() True. Responsif terhadap permintaan stop.
    """
    # 1. Putar semua layar splash secara berurutan (selalu tampil penuh).
    for (b0, b1, center) in SPLASH_SCREENS:
        if should_stop():
            return
        if center:
            _lcd_show(_center16(b0), _center16(b1))
        else:
            _lcd_show(b0, b1)            # rata kiri (ljust otomatis di writer)
        if _stop_event.wait(timeout=SPLASH_SECONDS):
            return                       # stop diminta saat menunggu

    # 2. Tahan sampai sistem benar-benar siap (loading bisa 5-10 dtk).
    dots = 0
    while not system_ready():
        if should_stop():
            return
        anim = "." * (dots % 4)
        _lcd_show(_center16("Menyiapkan"), _center16("sistem" + anim))
        dots += 1
        if _stop_event.wait(timeout=0.5):
            return

    log("Splash selesai — sistem siap, beralih ke tampilan utama.")

def lcd_close():
    if _lcd is not None:
        try:
            with _lcd_lock:
                _lcd.close(clear=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  THREAD LCD — SATU-SATUNYA PENULIS LCD  (Berat baris-0, Jenis baris-1)
# ═══════════════════════════════════════════════════════════════════════════════
def thread_lcd_refresh():
    """
    Satu-satunya thread yang boleh menulis ke LCD.
      Mode NORMAL   → baris-0 berat, baris-1 jenis (refresh tiap TICK).
      Mode OVERRIDE → pesan sementara (mis. 'Mengirim..') selama `durasi` detik.
    Perintah ("shutdown",) dari main → tulis pesan akhir lalu keluar.
    """
    log("Thread LCD: mulai (satu-satunya penulis LCD).")

    # ── FASE SPLASH BOOTING — tahan sampai sistem siap (atau stop diminta) ──
    _run_splash()
    if should_stop():
        log("Thread LCD: stop saat splash — keluar.", "INFO")
        return

    # Buang perintah yang sempat menumpuk selama splash (mis. tombol tak sengaja),
    # agar tampilan utama tidak langsung tertimpa pesan basi.
    while True:
        try:
            _lcd_cmd_queue.get_nowait()
        except queue.Empty:
            break

    override_until = 0.0
    TICK           = 0.1

    while True:
        now = time.time()

        # Proses semua perintah yang masuk di queue
        while True:
            try:
                cmd = _lcd_cmd_queue.get_nowait()
            except queue.Empty:
                break

            if cmd[0] == "shutdown":
                try:
                    with _lcd_lock:
                        _lcd_write_unsafe(0, "Sistem Mati...  ")
                        _lcd_write_unsafe(1, "                ")
                except Exception:
                    pass
                log("Thread LCD: berhenti.")
                return

            elif cmd[0] == "override":
                _, b0, b1, durasi = cmd
                override_until = (now + durasi) if durasi > 0 else float("inf")
                try:
                    with _lcd_lock:
                        _lcd_write_unsafe(0, b0)
                        _lcd_write_unsafe(1, b1)
                except Exception as e:
                    log(f"LCD override error: {e}", "WARN")

        # Tentukan mode aktif
        if now < override_until:
            pass  # Mode OVERRIDE — tidak tulis ulang
        else:
            if override_until != 0.0:
                override_until = 0.0
                try:
                    with _lcd_lock:
                        _lcd.clear()
                except Exception:
                    pass

            berat = get_state("berat_kg")
            jenis = get_state("jenis")
            jenis_disp = jenis.title() if (jenis and jenis != "...") else "-"
            try:
                with _lcd_lock:
                    _lcd_write_unsafe(0, f"Berat: {berat:6.2f} KG")
                    _lcd_write_unsafe(1, f"Jenis: {jenis_disp[:9]}")
            except Exception as e:
                log(f"LCD normal error: {e}", "WARN")

        # Bangun langsung saat stop diminta (tidak menunggu TICK penuh).
        _stop_event.wait(timeout=TICK)
        if _stop_event.is_set() and _lcd_cmd_queue.empty():
            log("Thread LCD: stop diminta — keluar.", "INFO")
            return


# ═══════════════════════════════════════════════════════════════════════════════
#  THREAD BERAT (HX711) — FILTER ANTI-NOISE + STABLE LOCK (v4)
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
    """Kembalikan sampel inti setelah membuang trim_ratio bagian ter-tinggi & ter-rendah."""
    if not values:
        return []
    s = sorted(values)
    k = int(len(s) * trim_ratio)
    if (len(s) - 2 * k) >= 1 and k > 0:
        return s[k:len(s) - k]
    return s


def _hx711_tare(hx: HX711) -> float:
    """Ambil nilai tare (offset) memakai trimmed median agar tahan outlier."""
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


def _read_grams_and_spread(hx: HX711, tare_val: float):
    """Baca satu siklus → (gram_median, spread_gram). (None,None) jika gagal."""
    raws = _hx711_read_raw_samples(hx, RAW_SAMPLES_PER_READ)
    if len(raws) < 3:
        return None, None

    core  = _trim_core(raws, TRIM_RATIO)
    grams = [(r - tare_val) / CALIBRATION_FACTOR for r in core]
    if not grams:
        return None, None

    gram_med = statistics.median(grams)
    spread   = max(grams) - min(grams)
    return gram_med, spread


class WeightFilter:
    """
    Filter berat dengan stable lock — seperti timbangan digital komersial.
    Alur: gerbang kestabilan (opsional) → deadband nol → rolling median →
          konfirmasi lompatan → stable lock (kunci tampilan setelah stabil).
    """
    def __init__(self, stability_threshold_g: float):
        self._buf               = collections.deque(maxlen=MEDIAN_WINDOW)
        self._stable_kg         = 0.0
        self._pending_kg        = None
        self._pending_n         = 0
        self._stability_thresh  = stability_threshold_g
        self._blocked_count     = 0

        # Stable lock state
        self._locked            = False
        self._lock_value        = 0.0
        self._lock_history      = collections.deque(maxlen=LOCK_STABLE_CYCLES)

    def reset(self, new_threshold_g: Optional[float] = None):
        self._buf.clear()
        self._stable_kg    = 0.0
        self._pending_kg   = None
        self._pending_n    = 0
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
        self._locked = False
        self._lock_value = 0.0
        self._lock_history.clear()

    def update(self, gram_med: Optional[float], spread_g: Optional[float]) -> float:
        # Gagal baca → pertahankan nilai.
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
            if self._pending_kg is not None and abs(kg_med - self._pending_kg) < SPIKE_DELTA_KG:
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
                    log(f"Lock AKTIF — {self._lock_value:.2f} kg (range {r_max-r_min:.3f})")
        else:
            self._lock_history.clear()

        return self._lock_value if self._locked else self._stable_kg


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
    _berat_ready.set()   # tare selesai → komponen berat siap

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
                    "DEBUG"
                )

            if berat > AUTOTARE_ZERO_KG:
                last_nonzero_time = time.time()
            else:
                idle_duration = time.time() - last_nonzero_time
                if idle_duration >= AUTOTARE_IDLE_SEC:
                    log(
                        f"Auto-tare: idle {idle_duration:.0f}s ≥ {AUTOTARE_IDLE_SEC:.0f}s "
                        f"— tare ulang untuk koreksi drift...",
                        "INFO"
                    )
                    tare_val = _hx711_tare(hx)
                    if STABILITY_GATE_ENABLED:
                        stability_thresh = _measure_noise_baseline(hx, tare_val)
                    filt.reset(new_threshold_g=stability_thresh)
                    set_state("berat_kg", 0.0)
                    last_nonzero_time = time.time()
                    cycle_count = 0

            _stop_event.wait(timeout=INTERVAL_BERAT)
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
#  KAMERA + MODEL YOLOv5 TFLITE  (jenis v3) + PERBAIKAN MJPG/V4L2
# ═══════════════════════════════════════════════════════════════════════════════
def _open_camera():
    """
    Buka webcam dengan perbaikan COLOR CAST MAGENTA/UNGU:
      - backend V4L2 eksplisit (Linux/RPi) + fallback default
      - paksa FOURCC = MJPG SEBELUM set resolusi (banyak webcam USB hanya
        memberi warna benar lewat MJPG; default YUYV → ungu/magenta).
    Mencoba beberapa index. Return objek VideoCapture, atau None.
    """
    for idx in list(dict.fromkeys([WEBCAM_INDEX, 0, 1, 2, 3, 4])):
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            continue

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WEBCAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        try:
            _fc  = int(cap.get(cv2.CAP_PROP_FOURCC))
            _fcs = "".join(chr((_fc >> (8 * i)) & 0xFF) for i in range(4)).strip()
            _aw  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            _ah  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            log(f"Webcam index {idx}: format={_fcs or '?'} {_aw}x{_ah}")
            if _fcs.upper() != "MJPG":
                log("Format kamera bukan MJPG — jika warna ungu/magenta, "
                    "cek 'v4l2-ctl --list-formats-ext -d /dev/video0'.", "WARN")
        except Exception:
            pass
        return cap
    return None


def load_model(path):
    if not os.path.exists(path):
        log(f"Model tidak ditemukan: {path}", "WARN")
        log("Pastikan file best-fp32.tflite ada di folder 'model/'.", "WARN")
        sys.exit(1)
    log(f"Memuat model: {os.path.basename(path)}")
    interpreter = tflite.Interpreter(model_path=path, num_threads=NUM_THREADS)
    interpreter.allocate_tensors()
    inp  = interpreter.get_input_details()[0]
    outp = interpreter.get_output_details()[0]

    # Laporkan tipe data agar mudah verifikasi FP32 vs FP16 vs INT8.
    in_dtype  = np.dtype(inp['dtype']).name
    out_dtype = np.dtype(outp['dtype']).name
    in_quant  = inp.get('quantization', (0.0, 0))
    out_quant = outp.get('quantization', (0.0, 0))
    log(f"Model dimuat. Input {inp['shape']} dtype={in_dtype} | "
        f"Output {outp['shape']} dtype={out_dtype}")
    if in_dtype in ("uint8", "int8"):
        log(f"  Input TERKUANTISASI (scale={in_quant[0]}, zero={in_quant[1]}).", "INFO")
    if out_dtype in ("uint8", "int8"):
        log(f"  Output TERKUANTISASI (scale={out_quant[0]}, zero={out_quant[1]}).", "INFO")
    return interpreter, inp, outp


def preprocess(frame, inp_detail=None, size=INPUT_SIZE):
    """
    Letterbox frame → (size x size) lalu siapkan tensor sesuai dtype model.
      - FP32 / FP16 : float32 dinormalisasi 0..1   (kasus model best-fp32.tflite)
      - INT8 / UINT8: dikuantisasi pakai (scale, zero_point) dari model
    """
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(frame, (nw, nh))
    padded = np.full((size, size, 3), 114, dtype=np.uint8)
    top  = (size - nh) // 2
    left = (size - nw) // 2
    padded[top:top+nh, left:left+nw] = resized
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)

    # Tentukan dtype target dari detail input model (default float32 utk FP32/FP16).
    target_dtype = np.float32
    if inp_detail is not None:
        target_dtype = np.dtype(inp_detail['dtype']).type

    if target_dtype in (np.float32, np.float16):
        img = rgb.astype(np.float32) / 255.0
    else:
        # Input terkuantisasi (uint8/int8): q = real/scale + zero_point
        q_scale, q_zero = inp_detail.get('quantization', (1.0, 0))
        if q_scale in (0, 0.0):
            q_scale = 1.0 / 255.0   # fallback umum
        img = (rgb.astype(np.float32) / 255.0) / q_scale + q_zero
        img = np.clip(img, np.iinfo(target_dtype).min, np.iinfo(target_dtype).max)
        img = img.astype(target_dtype)

    img = np.expand_dims(img, 0)
    return img, scale, left, top


def xywh2xyxy_pixel(boxes, size=INPUT_SIZE):
    out = np.zeros_like(boxes)
    cx = boxes[:, 0] * size
    cy = boxes[:, 1] * size
    w  = boxes[:, 2] * size
    h  = boxes[:, 3] * size
    out[:, 0] = cx - w / 2
    out[:, 1] = cy - h / 2
    out[:, 2] = cx + w / 2
    out[:, 3] = cy + h / 2
    return out


def _nms(boxes_xywh, scores, iou_thresh):
    indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(), scores.tolist(), CONF_THRESH, iou_thresh
    )
    if isinstance(indices, np.ndarray):
        return indices.flatten().tolist()
    if isinstance(indices, (list, tuple)) and len(indices) > 0:
        return [i[0] if isinstance(i, (list, tuple)) else i for i in indices]
    return []


def postprocess(output, scale, pad_left, pad_top, orig_h, orig_w):
    preds     = output[0]
    obj_conf  = preds[:, 4]
    cls_probs = preds[:, 5:]
    cls_ids   = np.argmax(cls_probs, axis=1)
    cls_confs = cls_probs[np.arange(len(cls_probs)), cls_ids]
    scores    = obj_conf * cls_confs

    mask = scores > CONF_THRESH
    if not np.any(mask):
        return []

    preds   = preds[mask]
    scores  = scores[mask]
    cls_ids = cls_ids[mask]

    boxes_xyxy = xywh2xyxy_pixel(preds[:, :4], INPUT_SIZE)
    boxes_xyxy[:, 0] = (boxes_xyxy[:, 0] - pad_left) / scale
    boxes_xyxy[:, 1] = (boxes_xyxy[:, 1] - pad_top)  / scale
    boxes_xyxy[:, 2] = (boxes_xyxy[:, 2] - pad_left) / scale
    boxes_xyxy[:, 3] = (boxes_xyxy[:, 3] - pad_top)  / scale
    boxes_xyxy = np.clip(boxes_xyxy, 0, [orig_w, orig_h, orig_w, orig_h])

    boxes_xywh = boxes_xyxy.copy()
    boxes_xywh[:, 2] = boxes_xyxy[:, 2] - boxes_xyxy[:, 0]
    boxes_xywh[:, 3] = boxes_xyxy[:, 3] - boxes_xyxy[:, 1]

    keep = _nms(boxes_xywh, scores, IOU_THRESH)

    results = []
    for i in keep:
        x1, y1, x2, y2 = boxes_xyxy[i].astype(int)
        cid  = int(cls_ids[i])
        conf = float(scores[i])
        name = CLASS_NAMES[cid] if cid < len(CLASS_NAMES) else f"cls{cid}"
        results.append((x1, y1, x2, y2, name, conf))
    return results


def _jenis_terkonfirmasi(history: deque) -> str:
    """Jenis yang KONSISTEN muncul di semua frame dalam window, atau '...'."""
    if len(history) < CONFIRM_FRAMES:
        return "..."

    confirmed = None
    for names in history:
        s = set(names)
        confirmed = s if confirmed is None else confirmed & s

    if not confirmed:
        return "..."

    for name in CLASS_NAMES:
        if name in confirmed:
            return name
    return sorted(confirmed)[0]


def thread_jenis():
    """Loop kamera: baca → inferensi → update state jenis terkonfirmasi."""
    try:
        interpreter, inp_det, outp_det = load_model(MODEL_PATH)
    except SystemExit:
        log("Model gagal dimuat — menghentikan sistem.", "ERROR")
        request_stop()   # agar splash & main keluar bersih, tidak menggantung
        return

    log(f"Membuka webcam index {WEBCAM_INDEX}...")
    cap = _open_camera()
    if cap is None:
        log("Tidak ada webcam terdeteksi! Cek: ls /dev/video*", "WARN")
        request_stop()
        return
    log("Webcam aktif. Mulai deteksi...")
    _jenis_ready.set()   # model dimuat + kamera terbuka → komponen jenis siap

    history     = deque(maxlen=CONFIRM_FRAMES)
    last_jenis  = "..."
    _timed_once = False

    try:
        while not should_stop():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            orig_h, orig_w = frame.shape[:2]

            img, scale, pad_left, pad_top = preprocess(frame, inp_det)
            interpreter.set_tensor(inp_det['index'], img)
            _t0 = time.time()
            interpreter.invoke()
            _t_inf = time.time() - _t0
            output = interpreter.get_tensor(outp_det['index'])

            # Log kecepatan inferensi sekali (untuk gauge performa FP32 di CM4).
            if not _timed_once:
                log(f"Inferensi pertama: {_t_inf*1000:.0f} ms "
                    f"(~{1.0/max(_t_inf,1e-3):.1f} FPS inferensi murni). "
                    f"Capture {orig_w}x{orig_h}.")
                _timed_once = True

            # Dequantisasi output bila model terkuantisasi (FP32/FP16: dilewati).
            if np.dtype(outp_det['dtype']).name in ("uint8", "int8"):
                o_scale, o_zero = outp_det.get('quantization', (1.0, 0))
                if o_scale not in (0, 0.0):
                    output = (output.astype(np.float32) - o_zero) * o_scale

            detections = postprocess(output, scale, pad_left, pad_top, orig_h, orig_w)

            # Simpan frame & deteksi terakhir untuk capture saat tombol ditekan
            set_state("last_frame", frame.copy())
            set_state("last_detections", detections)

            # Update history & konfirmasi jenis
            names = sorted(set(n for (_, _, _, _, n, _) in detections))
            history.append(names)
            jenis = _jenis_terkonfirmasi(history)

            if jenis != last_jenis:
                set_state("jenis", jenis)
                last_jenis = jenis
                if jenis != "...":
                    confs = [c for (_, _, _, _, n, c) in detections if n == jenis]
                    avg = sum(confs) / len(confs) if confs else 0
                    log(f"Jenis terkonfirmasi: {jenis} (conf {avg:.2f})")
                else:
                    log("Jenis: tidak ada objek konsisten")
    except Exception as e:
        log(f"Thread Jenis error: {e}", "ERROR")
    finally:
        try:
            cap.release()
        except Exception:
            pass
        log("Thread Jenis berhenti.")


# ═══════════════════════════════════════════════════════════════════════════════
#  CAPTURE FOTO SAAT TOMBOL DITEKAN  (overlay kotak + berat & jenis)
# ═══════════════════════════════════════════════════════════════════════════════
def capture_on_button(frame, detections, berat_kg: float, jenis: str) -> Optional[str]:
    """Simpan foto + bounding box + overlay (berat & jenis) ke captures/."""
    if frame is None:
        log("Tidak ada frame untuk di-capture.", "WARN")
        return None

    img = frame.copy()
    for (x1, y1, x2, y2, name, conf) in (detections or []):
        color = CLASS_COLORS.get(name, (255, 255, 0))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{name}: {conf:.2f}"
        cv2.putText(img, label, (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Overlay ringkasan berat + jenis di pojok bawah
    jenis_txt = jenis if (jenis and jenis != "...") else "-"
    overlay = f"{berat_kg:.2f} kg | {jenis_txt}"
    cv2.putText(img, overlay, (8, img.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    ts       = time.strftime("%Y%m%d_%H%M%S")
    jenis_fn = jenis if (jenis and jenis != "...") else "nodetect"
    filename = f"{jenis_fn}_{berat_kg:.2f}kg_{ts}.jpg"
    path     = os.path.join(CAPTURE_DIR, filename)

    try:
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        log(f"Foto disimpan: {filename}")
        return path
    except Exception as ex:
        log(f"Gagal simpan foto: {ex}", "WARN")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  KIRIM DATA GABUNGAN (berat + jenis + foto) KE GOOGLE APPS SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════
def kirim_semua(berat_kg: float, jenis_str: str, image_path: Optional[str]) -> Tuple[bool, str]:
    """
    Kirim SATU baris gabungan: berat + jenis + foto dalam SATU POST request.
    Skema payload 5-kunci identik dengan sistem awal → endpoint GAS tetap kompatibel.
    GAS redirect 302 → diikuti GET untuk mengambil body JSON.
    Return (sukses, foto_url).
    """
    jenis_kirim = (
        jenis_str.split(",")[0].strip() if jenis_str and jenis_str != "..." else ""
    )

    image_b64 = ""
    filename  = ""
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            filename = os.path.basename(image_path)
            log(f"Foto dikodekan: {filename} ({len(image_b64) // 1024} KB base64)")
        except Exception as ex:
            log(f"Gagal encode foto: {ex}", "WARN")

    payload = {
        "berat"     : f"{berat_kg:.2f}",
        "jenis"     : jenis_kirim,
        "filename"  : filename,
        "imageData" : image_b64,
        "folderName": GOOGLE_DRIVE_FOLDER_NAME,
    }

    # Sertakan token hanya bila dikonfigurasi → tetap kompatibel dengan
    # deployment Apps Script lama yang belum memakai token.
    if GAS_SHARED_TOKEN:
        payload["token"] = GAS_SHARED_TOKEN

    log(
        f"Kirim → berat={berat_kg:.2f}kg | jenis={jenis_kirim or '-'}"
        + (f" | foto={filename}" if filename else " | foto=tidak ada")
    )

    try:
        resp = requests.post(
            GOOGLE_SHEETS_URL,
            json=payload,
            allow_redirects=False,
            timeout=45,
        )

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            if location:
                resp = requests.get(location, allow_redirects=False, timeout=15)

        if resp.status_code == 200:
            try:
                data     = resp.json()
                foto_url = data.get("fileUrl", "")
                if data.get("status") == "OK":
                    foto_info = ("ada → " + foto_url[:50]) if foto_url else "tidak ada"
                    log(f"✓ Berhasil! foto={foto_info}")
                    return True, foto_url
                else:
                    log(f"✗ GAS error: {data.get('message', '?')}", "WARN")
                    return False, ""
            except Exception:
                log("✓ Berhasil (response non-JSON diabaikan)")
                return True, ""
        else:
            log(f"✗ HTTP {resp.status_code}: {resp.text[:80]}", "WARN")
            return False, ""

    except requests.exceptions.Timeout:
        log("✗ Timeout — koneksi lambat atau foto terlalu besar", "WARN")
        return False, ""
    except requests.exceptions.ConnectionError:
        log("✗ Tidak terhubung — cek WiFi/LAN", "WARN")
        return False, ""
    except Exception as ex:
        log(f"✗ Error: {ex}", "WARN")
        return False, ""


# ═══════════════════════════════════════════════════════════════════════════════
#  PUSH BUTTON — CALLBACK GPIO  (kirim GABUNGAN berat + jenis + foto)
# ═══════════════════════════════════════════════════════════════════════════════
_last_btn_time = 0.0
_kirim_lock    = threading.Lock()

def _btn_callback(channel: int):
    """
    Dipanggil saat GPIO falling edge. Tidak menulis LCD langsung, tidak sleep.
    Double-submit dilindungi oleh _kirim_lock + software debounce.
    """
    global _last_btn_time
    now = time.time()

    if now - _last_btn_time < DEBOUNCE_MS / 1000.0:
        return
    _last_btn_time = now

    if not _kirim_lock.acquire(blocking=False):
        log("Tombol diabaikan — pengiriman sebelumnya masih berlangsung.", "WARN")
        return

    berat = get_state("berat_kg")
    jenis = get_state("jenis")
    log(f"Tombol ditekan! Berat={berat:.2f}kg | Jenis={jenis}")

    _lcd_cmd_queue.put(("override", "Mengirim data.. ", "Mohon tunggu... ", 0))

    threading.Thread(
        target=_kirim_dan_tampilkan,
        args=(berat, jenis),
        daemon=True,
        name="Thread-Kirim",
    ).start()


def _kirim_dan_tampilkan(berat: float, jenis: str):
    """Dijalankan di thread terpisah. _kirim_lock dilepas di finally."""
    try:
        frame      = get_state("last_frame")
        detections = get_state("last_detections")
        local_path = capture_on_button(frame, detections, berat, jenis)
        sukses, foto_url = kirim_semua(berat, jenis, local_path)

        jenis_disp = jenis.title() if (jenis and jenis != "...") else "-"
        if sukses and foto_url:
            baris0 = "TERKIRIM + FOTO!"
            baris1 = f"{berat:.1f}kg {jenis_disp[:8]}"
        elif sukses:
            baris0 = "TERKIRIM!       "
            baris1 = f"{berat:.1f}kg {jenis_disp[:8]}"
        else:
            baris0 = "GAGAL KIRIM!    "
            baris1 = "Cek WiFi/Script "

        _lcd_cmd_queue.put(("override", baris0, baris1, 2.0))

    finally:
        _kirim_lock.release()


def btn_setup():
    GPIO.setup(BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        BTN_PIN,
        GPIO.FALLING,
        callback=_btn_callback,
        bouncetime=DEBOUNCE_MS,
    )
    log(f"Push button siap di GPIO{BTN_PIN} (aktif rendah, pull-up internal)")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    log("=" * 55)
    log("  TIMBANGAN IOT TERINTEGRASI — Berat + Jenis  (v5.0)")
    log(f"  Folder: {_ROOT_DIR}")
    log("=" * 55)

    # 1. Inisialisasi GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # 2. Inisialisasi LCD
    lcd_init()

    # 3. Setup push button
    btn_setup()

    # 4. Jalankan thread berat (HX711)
    t_berat = threading.Thread(target=thread_berat, name="Thread-Berat", daemon=True)
    t_berat.start()
    log("Thread Berat dimulai.")

    # 5. Jalankan thread jenis (kamera + deteksi)
    t_jenis = threading.Thread(target=thread_jenis, name="Thread-Jenis", daemon=True)
    t_jenis.start()
    log("Thread Jenis dimulai.")

    # 6. Jalankan thread LCD
    t_lcd = threading.Thread(target=thread_lcd_refresh, name="Thread-LCD", daemon=True)
    t_lcd.start()
    log("Thread LCD dimulai.")

    log("Sistem siap. Tekan CTRL+C untuk keluar.")
    log(f"Tombol kirim (berat + jenis + foto): GPIO{BTN_PIN}")

    try:
        while True:
            time.sleep(1)
            if should_stop():
                log("Stop event terdeteksi, keluar dari main loop.", "WARN")
                break

    except KeyboardInterrupt:
        log("\nCTRL+C diterima, menutup sistem...")

    finally:
        # Urutan shutdown yang aman:
        request_stop()                      # 1. sinyal stop ke semua thread
        _lcd_cmd_queue.put(("shutdown",))   # 2. perintah shutdown ke thread LCD
        t_lcd.join(timeout=3.0)             # 3. tunggu thread LCD selesai
        t_jenis.join(timeout=3.0)           # 4. tunggu thread Jenis (lepas kamera)
        t_berat.join(timeout=3.0)           # 5. tunggu thread Berat (power-down HX711)
        lcd_close()                         # 6. tutup LCD
        GPIO.cleanup()                      # 7. bersihkan GPIO
        log("Sistem dimatikan. Selesai.")


if __name__ == "__main__":
    main()
