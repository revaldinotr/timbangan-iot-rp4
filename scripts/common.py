#!/usr/bin/env python3
"""
scripts/common.py — Fondasi bersama: KONFIGURASI + LOGGER + SHARED STATE.

AMAN DI-COMMIT KE GITHUB.
Tidak ada satu pun kredensial di file ini. Nilai rahasia dibaca dari
environment variable (atau file `.env` yang TIDAK ikut di-commit).

    cp .env.example .env
    nano .env          # isi GOOGLE_SHEETS_SCRIPT_ID milikmu

Modul ini sengaja TIDAK meng-import hardware apa pun (GPIO/HX711/cv2), sehingga
bisa dipakai main.py, thread_berat.py, thread_jenis.py, dan IoT.py tanpa saling
bergantung — menghindari circular import.
"""

import os
import sys
import threading
from datetime import datetime

# Izinkan tiap script di folder scripts/ dijalankan mandiri:
#   python3 scripts/thread_berat.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Muat file .env bila python-dotenv terpasang (opsional, tidak wajib).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
except ImportError:
    pass


def _env(key: str, default):
    """Ambil env var, konversi otomatis mengikuti tipe `default`."""
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on", "y")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return raw


# ═══════════════════════════════════════════════════════════════════════════════
#  RAHASIA — WAJIB dari environment. Kosong = fitur IoT nonaktif otomatis.
# ═══════════════════════════════════════════════════════════════════════════════
# Script ID dari URL: script.google.com/macros/s/<SCRIPT_ID>/exec
GOOGLE_SHEETS_SCRIPT_ID  = _env("GOOGLE_SHEETS_SCRIPT_ID", "")
GOOGLE_SHEETS_URL        = (
    f"https://script.google.com/macros/s/{GOOGLE_SHEETS_SCRIPT_ID}/exec"
    if GOOGLE_SHEETS_SCRIPT_ID else ""
)
GOOGLE_DRIVE_FOLDER_NAME = _env("GOOGLE_DRIVE_FOLDER_NAME", "Captures Data Sayur")
UPLOAD_TIMEOUT           = _env("UPLOAD_TIMEOUT", 45)


def iot_enabled() -> bool:
    """True bila Script ID sudah diisi lewat environment / .env."""
    return bool(GOOGLE_SHEETS_SCRIPT_ID)


# ═══════════════════════════════════════════════════════════════════════════════
#  IDENTITAS / SPLASH  (bukan rahasia, tapi personal → boleh diganti lewat .env)
# ═══════════════════════════════════════════════════════════════════════════════
SPLASH_SECONDS = _env("SPLASH_SECONDS", 2.0)
# Tiap entri: (baris_atas, baris_bawah, rata_tengah?)
SPLASH_SCREENS = [
    (_env("SPLASH1_TOP", "Timbangan IoT"), _env("SPLASH1_BOT", "Polsri 2026"), True),
    (_env("SPLASH2_TOP", "Nama 1"),        _env("SPLASH2_BOT", "NIM 1"),       False),
    (_env("SPLASH3_TOP", "Nama 2"),        _env("SPLASH3_BOT", "NIM 2"),       False),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  HARDWARE: GPIO & HX711 (load cell)
# ═══════════════════════════════════════════════════════════════════════════════
HX_DOUT            = _env("HX_DOUT", 17)     # GPIO pin DOUT HX711
HX_SCK             = _env("HX_SCK", 27)      # GPIO pin SCK HX711
CALIBRATION_FACTOR = _env("CALIBRATION_FACTOR", 24.1850)  # hasil skrip kalibrasi
NOISE_THRESHOLD_KG = 0.02     # Di bawah nilai ini dianggap nol / noise
TARE_SAMPLES       = 15       # Jumlah sampel untuk tare awal
INTERVAL_BERAT     = 0.05     # Interval antar siklus baca (detik)
AUTOTARE_IDLE_SEC  = 120.0    # Idle berapa detik sebelum auto-tare
AUTOTARE_ZERO_KG   = 0.05     # Batas "dianggap kosong" untuk memulai auto-tare

# ── Filter anti-noise (sentuhan konektor / EMI) ──
RAW_SAMPLES_PER_READ   = 5     # 5 sampel × ~100ms = ~0.5s per siklus
RAW_SAMPLE_DELAY       = 0.0
TRIM_RATIO             = 0.20  # Dari 5 sampel: buang 1 tertinggi + 1 terendah
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


# ═══════════════════════════════════════════════════════════════════════════════
#  HARDWARE: LCD I2C 16x2 & Push button
# ═══════════════════════════════════════════════════════════════════════════════
LCD_ADDR = int(str(_env("LCD_ADDR", "0x27")), 0)   # cek: i2cdetect -y 1
LCD_COLS = 16
LCD_ROWS = 2

BTN_PIN     = _env("BTN_PIN", 22)   # GPIO tombol (aktif rendah, pull-up internal)
DEBOUNCE_MS = 300                   # Software debounce tambahan (ms)


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL YOLOv5 TFLITE & KAMERA
# ═══════════════════════════════════════════════════════════════════════════════
MODEL_PATH   = _env("MODEL_PATH", os.path.join(ROOT_DIR, "model", "best-fp16.tflite"))
CLASS_NAMES  = ["kentang", "tomat", "wortel"]
CLASS_COLORS = {
    "kentang": (0, 200, 0),    # hijau
    "tomat"  : (0,  60, 255),  # merah
    "wortel" : (0, 165, 255),  # oranye
}
CONF_THRESH  = _env("CONF_THRESH", 0.08)  # Confidence threshold deteksi
IOU_THRESH   = _env("IOU_THRESH", 0.15)   # IOU threshold NMS
INPUT_SIZE   = 640    # Ukuran input model (px) — ditentukan saat export
NUM_THREADS  = _env("NUM_THREADS", 4)     # CM4/RPi4 = 4 core Cortex-A72
WEBCAM_INDEX = _env("WEBCAM_INDEX", 0)    # USB webcam → /dev/video0

# Resolusi CAPTURE kamera (DIPISAH dari ukuran input model).
#   1280x720  : keseimbangan (disarankan RPi4 2GB)  ← default
#   1920x1080 : detail maksimal objek jauh, CPU & RAM lebih berat
#   640x480   : ringan, objek jauh sering terlewat
WEBCAM_WIDTH   = _env("WEBCAM_WIDTH", 1280)
WEBCAM_HEIGHT  = _env("WEBCAM_HEIGHT", 720)
CONFIRM_FRAMES = _env("CONFIRM_FRAMES", 8)  # Frame konsisten utk konfirmasi jenis


# ═══════════════════════════════════════════════════════════════════════════════
#  PENYIMPANAN LOKAL
# ═══════════════════════════════════════════════════════════════════════════════
CAPTURE_DIR  = os.path.join(ROOT_DIR, "captures")
LOG_DIR      = os.path.join(ROOT_DIR, "logs")
JPEG_QUALITY = _env("JPEG_QUALITY", 70)   # Kompresi foto (hemat upload base64)


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
            logfile = os.path.join(
                LOG_DIR, f"main_{datetime.now().strftime('%Y%m%d')}.log"
            )
            with open(logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED STATE (thread-safe)
# ═══════════════════════════════════════════════════════════════════════════════
_lock  = threading.Lock()
_state = {
    "berat_kg"       : 0.0,    # berat tampil (nilai terkunci saat stabil)
    "locked"         : False,  # status kunci-stabil filter berat
    "jenis"          : "...",  # jenis terkonfirmasi saat ini
    "last_frame"     : None,   # frame BGR terakhir dari kamera
    "last_detections": [],     # [(x1, y1, x2, y2, name, conf), ...]
}


def get_state(key):
    with _lock:
        return _state[key]


def set_state(key, val):
    with _lock:
        _state[key] = val


# ═══════════════════════════════════════════════════════════════════════════════
#  SINYAL SHUTDOWN (lock-free, atomic)
# ═══════════════════════════════════════════════════════════════════════════════
stop_event = threading.Event()


def is_running() -> bool:
    return not stop_event.is_set()


def should_stop() -> bool:
    return stop_event.is_set()


def request_stop():
    stop_event.set()


# ═══════════════════════════════════════════════════════════════════════════════
#  SINYAL "SISTEM SIAP" (menahan splash sampai loading selesai)
# ═══════════════════════════════════════════════════════════════════════════════
berat_ready = threading.Event()   # di-set setelah tare HX711 selesai
jenis_ready = threading.Event()   # di-set setelah model dimuat + kamera dibuka


def system_ready() -> bool:
    """True bila tare HX711 selesai DAN model + kamera siap."""
    return berat_ready.is_set() and jenis_ready.is_set()
