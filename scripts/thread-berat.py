# Program Utama Timbangan IoT (Thread Pembacaan Berat)
# File: thread-berat.py

import time
import threading
import queue
import statistics
import collections
import requests
import RPi.GPIO as GPIO
from hx711 import HX711
from RPLCD.i2c import CharLCD


# ---------- KONFIGURASI ----------
GOOGLE_SHEETS_URL        = "..."
GOOGLE_DRIVE_FOLDER_NAME = "..."

HX_DOUT            = 17
HX_SCK             = 27
CALIBRATION_FACTOR = 24.1850
NOISE_THRESHOLD_KG = 0.02
TARE_SAMPLES       = 15
INTERVAL_BERAT     = 0.05

RAW_SAMPLES_PER_READ = 5
TRIM_RATIO           = 0.20
MEDIAN_WINDOW        = 3
DEADBAND_KG          = 0.05

LOCK_TOLERANCE_KG     = 0.20
LOCK_STABLE_CYCLES    = 4
LOCK_RELEASE_DELTA_KG = 1.0
LOCK_RELEASE_ZERO_KG  = 0.15

LCD_ADDR = 0x27
LCD_COLS = 16
LCD_ROWS = 2

BTN_PIN     = 22
DEBOUNCE_MS = 300


# ---------- STATE BERSAMA ANTAR THREAD ----------
_lock  = threading.Lock()
_state = {"berat_kg": 0.0, "locked": False}

def get_state(key):
    with _lock:
        return _state[key]

def set_state(key, val):
    with _lock:
        _state[key] = val

_stop_event = threading.Event()


# ---------- LCD ----------
_lcd = None
_lcd_lock = threading.Lock()
_lcd_queue: queue.Queue = queue.Queue()

def lcd_init():
    global _lcd
    _lcd = CharLCD(i2c_expander='PCF8574', address=LCD_ADDR, port=1,
                   cols=LCD_COLS, rows=LCD_ROWS, charmap='A02',
                   auto_linebreaks=True, backlight_enabled=True)
    with _lcd_lock:
        _lcd.clear()
        _lcd_write(0, "Berat:   0.00 KG")

def _lcd_write(row, text):
    text = str(text).ljust(LCD_COLS)[:LCD_COLS]
    _lcd.cursor_pos = (row, 0)
    _lcd.write_string(text)

def lcd_close():
    with _lcd_lock:
        _lcd.close(clear=True)

def thread_lcd():
    """Thread khusus penulis LCD (normal & override)."""
    override_until = 0.0
    while not _stop_event.is_set():
        now = time.time()
        try:
            _, b0, b1, durasi = _lcd_queue.get_nowait()
            override_until = now + durasi
            with _lcd_lock:
                _lcd_write(0, b0)
                _lcd_write(1, b1)
        except queue.Empty:
            pass

        if now >= override_until:
            berat  = get_state("berat_kg")
            locked = get_state("locked")
            with _lcd_lock:
                _lcd_write(0, f"Berat: {berat:6.2f} KG")
                if locked:
                    _lcd_write(1, ">> STABIL <<    ")
                elif berat > NOISE_THRESHOLD_KG:
                    _lcd_write(1, "   Menimbang... ")
                else:
                    _lcd_write(1, "                ")
        time.sleep(0.1)


# ---------- PEMBACAAN SENSOR HX711 ----------
def _baca_sampel(hx, n):
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        if raw is not False and raw is not None:
            vals.append(raw)
    return vals

def _trim(values, ratio):
    """Buang sampel tertinggi & terendah."""
    if not values:
        return []
    s = sorted(values)
    k = int(len(s) * ratio)
    if (len(s) - 2 * k) >= 1 and k > 0:
        return s[k:len(s) - k]
    return s

def hx711_tare(hx):
    raws = _baca_sampel(hx, TARE_SAMPLES)
    core = _trim(raws, TRIM_RATIO)
    return statistics.median(core) if core else 0.0

def baca_gram(hx, tare):
    raws = _baca_sampel(hx, RAW_SAMPLES_PER_READ)
    if len(raws) < 3:
        return None
    core  = _trim(raws, TRIM_RATIO)
    grams = [(r - tare) / CALIBRATION_FACTOR for r in core]
    return statistics.median(grams) if grams else None


# ---------- FILTER BERAT DENGAN STABLE LOCK ----------
class WeightFilter:
    """Deadband nol -> rolling median -> stable lock."""

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

        # Jika sedang TERKUNCI
        if self._locked:
            if kg_med < LOCK_RELEASE_ZERO_KG:
                self._locked = False
                self._stable_kg = 0.0
                self._buf.clear()
                self._lock_history.clear()
                return 0.0
            if abs(kg_med - self._lock_value) > LOCK_RELEASE_DELTA_KG:
                self._locked = False
                self._lock_history.clear()
                self._stable_kg = kg_med
                return self._stable_kg
            return self._lock_value

        # Jika TIDAK terkunci
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


def thread_berat():
    """Thread pembacaan sensor secara terus-menerus."""
    hx = HX711(HX_DOUT, HX_SCK)
    tare = hx711_tare(hx)
    filt = WeightFilter()
    print("Sensor siap.")

    while not _stop_event.is_set():
        gram  = baca_gram(hx, tare)
        berat = filt.update(gram)
        set_state("berat_kg", berat)
        set_state("locked", filt.is_locked)
        time.sleep(INTERVAL_BERAT)

    hx.power_down()


# ---------- PENGIRIMAN KE GOOGLE SHEETS ----------
def kirim_berat(berat_kg):
    payload = {
        "berat"     : f"{berat_kg:.2f}",
        "jenis"     : "",
        "filename"  : "",
        "imageData" : "",
        "folderName": GOOGLE_DRIVE_FOLDER_NAME,
    }
    try:
        resp = requests.post(GOOGLE_SHEETS_URL, json=payload,
                             allow_redirects=False, timeout=45)
        if resp.status_code in (301, 302, 303, 307, 308):
            lokasi = resp.headers.get("Location", "")
            if lokasi:
                resp = requests.get(lokasi, allow_redirects=False, timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


# ---------- PUSH BUTTON ----------
_last_btn_time = 0.0
_kirim_lock    = threading.Lock()

def _btn_callback(channel):
    global _last_btn_time
    now = time.time()
    if now - _last_btn_time < DEBOUNCE_MS / 1000.0:
        return
    _last_btn_time = now

    if not _kirim_lock.acquire(blocking=False):
        return

    berat = get_state("berat_kg")
    _lcd_queue.put(("override", "Mengirim berat..", "Mohon tunggu... ", 0))
    threading.Thread(target=_proses_kirim, args=(berat,), daemon=True).start()

def _proses_kirim(berat):
    try:
        if kirim_berat(berat):
            _lcd_queue.put(("override", "TERKIRIM!       ", f"Berat: {berat:6.2f}KG", 2))
        else:
            _lcd_queue.put(("override", "GAGAL KIRIM!    ", "Cek WiFi/Script ", 2))
    finally:
        _kirim_lock.release()

def btn_setup():
    GPIO.setup(BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BTN_PIN, GPIO.FALLING,
                          callback=_btn_callback, bouncetime=DEBOUNCE_MS)


# ---------- PROGRAM UTAMA ----------
def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    lcd_init()
    btn_setup()

    threading.Thread(target=thread_berat, daemon=True).start()
    threading.Thread(target=thread_lcd, daemon=True).start()

    print("Sistem siap. Tekan CTRL+C untuk keluar.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMenutup sistem...")
    finally:
        _stop_event.set()
        time.sleep(0.3)
        lcd_close()
        GPIO.cleanup()
        print("Selesai.")


if __name__ == "__main__":
    main()
