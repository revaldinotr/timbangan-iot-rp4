#!/usr/bin/env python3
"""
main.py — TIMBANGAN IOT TERINTEGRASI (Berat + Jenis Sayur)
Raspberry Pi 4 · HX711 · LCD I2C 16x2 · USB Webcam · YOLOv5n TFLite FP16

AMAN DI-COMMIT KE GITHUB: tidak ada Script ID, token, atau kredensial apa pun
di file ini. Semua dibaca dari scripts/common.py → environment / file .env.

Tanggung jawab file ini HANYA orkestrasi:
    • inisialisasi GPIO
    • LCD I2C 16x2 (satu-satunya penulis LCD ada di thread_lcd_refresh)
    • push button + debounce
    • start/stop tiga thread pekerja
    • shutdown bersih

Logika detail ada di modul terpisah:
    scripts/thread_berat.py   — pembacaan HX711 + Stable Lock  (tanpa IoT)
    scripts/thread_jenis.py   — YOLOv5 TFLite + webcam          (tanpa IoT)
    scripts/IoT.py            — kirim foto & data ke cloud
    scripts/common.py         — konfigurasi, logger, shared state

Jalankan:
    cp .env.example .env && nano .env      # isi GOOGLE_SHEETS_SCRIPT_ID
    python3 main.py
"""

import sys
import time
import queue
import threading

from scripts.common import (
    # konfigurasi
    LCD_ADDR, LCD_COLS, LCD_ROWS, SPLASH_SECONDS, SPLASH_SCREENS,
    BTN_PIN, DEBOUNCE_MS, ROOT_DIR, iot_enabled,
    # runtime
    log, get_state, stop_event, should_stop, request_stop, system_ready,
)
from scripts.thread_berat import thread_berat
from scripts.thread_jenis import thread_jenis, capture_frame
from scripts.IoT import kirim_semua

# ── Import GPIO ──────────────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("[ERROR] RPi.GPIO tidak ditemukan! pip install RPi.GPIO")
    sys.exit(1)

# ── Import LCD (RPLCD / CharLCD) ─────────────────────────────────────────────
try:
    from RPLCD.i2c import CharLCD
    RPLCD_AVAILABLE = True
except ImportError:
    CharLCD = None
    RPLCD_AVAILABLE = False
    print("[WARN] RPLCD tidak terinstall. LCD dinonaktifkan.")


# ═══════════════════════════════════════════════════════════════════════════════
#  LCD HELPER
# ═══════════════════════════════════════════════════════════════════════════════
_lcd      = None
_lcd_lock = threading.Lock()

# Format item queue:
#   ("override", baris0, baris1, durasi_detik)  — tampilkan sementara
#   ("shutdown",)                               — tulis pesan akhir lalu keluar
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
            backlight_enabled=True,
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


def lcd_close():
    if _lcd is not None:
        try:
            with _lcd_lock:
                _lcd.close(clear=True)
        except Exception:
            pass


def _run_splash():
    """
    Fase booting: tampilkan layar splash satu per satu (tiap SPLASH_SECONDS),
    lalu — bila model/tare BELUM siap — tahan di layar 'Menyiapkan...' (animasi
    titik) sampai system_ready() True. Responsif terhadap permintaan stop.
    """
    for (b0, b1, center) in SPLASH_SCREENS:
        if should_stop():
            return
        if center:
            _lcd_show(_center16(b0), _center16(b1))
        else:
            _lcd_show(b0, b1)            # rata kiri (ljust otomatis di writer)
        if stop_event.wait(timeout=SPLASH_SECONDS):
            return                       # stop diminta saat menunggu

    dots = 0
    while not system_ready():
        if should_stop():
            return
        anim = "." * (dots % 4)
        _lcd_show(_center16("Menyiapkan"), _center16("sistem" + anim))
        dots += 1
        if stop_event.wait(timeout=0.5):
            return

    log("Splash selesai — sistem siap, beralih ke tampilan utama.")


# ═══════════════════════════════════════════════════════════════════════════════
#  THREAD LCD — SATU-SATUNYA PENULIS LCD  (Berat baris-0, Jenis baris-1)
# ═══════════════════════════════════════════════════════════════════════════════
def thread_lcd_refresh():
    """
    Mode NORMAL   → baris-0 berat, baris-1 jenis (refresh tiap TICK).
    Mode OVERRIDE → pesan sementara (mis. 'Mengirim..') selama `durasi` detik.
    Perintah ("shutdown",) dari main → tulis pesan akhir lalu keluar.
    """
    log("Thread LCD: mulai (satu-satunya penulis LCD).")

    _run_splash()
    if should_stop():
        log("Thread LCD: stop saat splash — keluar.")
        return

    # Buang perintah yang menumpuk selama splash (mis. tombol tak sengaja),
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

        # Proses semua perintah yang masuk di queue.
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

            if cmd[0] == "override":
                _, b0, b1, durasi = cmd
                override_until = (now + durasi) if durasi > 0 else float("inf")
                try:
                    with _lcd_lock:
                        _lcd_write_unsafe(0, b0)
                        _lcd_write_unsafe(1, b1)
                except Exception as e:
                    log(f"LCD override error: {e}", "WARN")

        # Tentukan mode aktif.
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
        stop_event.wait(timeout=TICK)
        if stop_event.is_set() and _lcd_cmd_queue.empty():
            log("Thread LCD: stop diminta — keluar.")
            return


# ═══════════════════════════════════════════════════════════════════════════════
#  PUSH BUTTON — kirim GABUNGAN berat + jenis + foto
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
        local_path = capture_frame(frame, detections, berat, jenis)
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
    log("  TIMBANGAN IOT TERINTEGRASI — Berat + Jenis  (v5.1)")
    log(f"  Folder: {ROOT_DIR}")
    log("=" * 55)

    if not iot_enabled():
        log("GOOGLE_SHEETS_SCRIPT_ID kosong — mode OFFLINE, "
            "foto tetap disimpan lokal tapi tidak diunggah.", "WARN")

    # 1. Inisialisasi GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # 2. Inisialisasi LCD
    lcd_init()

    # 3. Setup push button
    btn_setup()

    # 4-6. Jalankan thread pekerja
    t_berat = threading.Thread(target=thread_berat,       name="Thread-Berat", daemon=True)
    t_jenis = threading.Thread(target=thread_jenis,       name="Thread-Jenis", daemon=True)
    t_lcd   = threading.Thread(target=thread_lcd_refresh, name="Thread-LCD",   daemon=True)

    t_berat.start(); log("Thread Berat dimulai.")
    t_jenis.start(); log("Thread Jenis dimulai.")
    t_lcd.start();   log("Thread LCD dimulai.")

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
