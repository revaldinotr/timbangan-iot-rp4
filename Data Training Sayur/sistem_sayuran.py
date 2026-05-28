#!/usr/bin/env python3
"""
========================================================
  SISTEM SAYURAN - Timbangan + Deteksi YOLOv5 TFLite
  Integrasi: timbangan_fixed.py + detect_rpi_led.py

  FIXED:
    - HX711 raw value checking (None/False) seperti timbangan_fixed.py
    - LCD charmap='A02' sesuai timbangan_fixed.py
    - BGR→RGB conversion untuk TFLite
    - Thread-safe variable dengan threading.Lock()
    - Auto-detect input shape model (NCHW/NHWC)
    - Pin GPIO disesuaikan (tidak bentrok LED, sesuai flowchart)
========================================================
"""

import RPi.GPIO as GPIO
import time
import threading
import requests
import statistics
import cv2
import numpy as np
from hx711 import HX711
from RPLCD.i2c import CharLCD

# TFLite - gunakan tflite_runtime jika tersedia, fallback ke tensorflow
try:
    from tflite_runtime import interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

# ================= KONFIGURASI =================
GOOGLE_SCRIPT_ID = "AKfycbwD-gl9NvYlJWm2e_2t-q6TnxEeofifMBSuHHWy8VZZLJuLq-mpUJ5Znmhp3oXd8WtcQg"

HX_DOUT    = 17   # Pin fisik 11
HX_SCK     = 27   # Pin fisik 13
PIN_BUTTON = 22   # Pin fisik 15

CALIBRATION_FACTOR = 23.95   # Hasil kalibrasi.py
NOISE_THRESHOLD_KG = 0.1
TARE_SAMPLES       = 15
READ_SAMPLES       = 5

MODEL_PATH   = "models/best-fp16.tflite"
CLASS_NAMES  = ["kentang", "tomat", "wortel"]
CONF_THRESHOLD = 0.5

# ================= VARIABEL GLOBAL =================
kg = 0.0
jenis_sayuran = "Menunggu..."
tare_val = 0.0
running = True
lock = threading.Lock()

# ================= LCD I2C =================
# Sesuai timbangan_fixed.py: charmap='A02'
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,
    port=1,
    cols=16,
    rows=2,
    dotsize=8,
    charmap='A02',
    auto_linebreaks=True,
    backlight_enabled=True
)

def lcd_clear_line(row):
    """Bersihkan satu baris LCD dengan spasi."""
    lcd.cursor_pos = (row, 0)
    lcd.write_string(' ' * 16)

def lcd_print(row, col, text):
    """Tulis teks ke posisi tertentu di LCD."""
    lcd.cursor_pos = (row, col)
    lcd.write_string(str(text)[:16 - col])

# ================= HX711 (tatobari API) =================
def hx711_read_raw_avg(hx, n=5):
    """Baca median n sampel raw. Skip None/False (FIXED)."""
    vals = []
    for _ in range(n):
        raw = hx.get_raw_data_mean(1)
        # FIXED: cek eksplisit None/False, bukan truthiness
        if raw is not None and raw is not False:
            vals.append(raw)
        time.sleep(0.01)
    if not vals:
        return None
    return statistics.median(vals)

def init_hx711():
    global hx, tare_val
    hx = HX711(HX_DOUT, HX_SCK)
    print("Taring HX711...")
    raw = hx711_read_raw_avg(hx, TARE_SAMPLES)
    if raw is not None:
        tare_val = raw
    else:
        tare_val = 0.0
        print("PERINGATAN: Tare gagal, offset diset ke 0")
    print(f"Tare offset = {tare_val:.1f}")

def get_kg():
    global kg
    raw = hx711_read_raw_avg(hx, READ_SAMPLES)
    if raw is None:
        return
    gram = (raw - tare_val) / CALIBRATION_FACTOR
    kg = max(0.0, gram / 1000.0)
    if kg < NOISE_THRESHOLD_KG:
        kg = 0.0

# ================= KAMERA + YOLO TFLite =================
def camera_detection_thread():
    global jenis_sayuran, running

    try:
        interp = tflite.Interpreter(model_path=MODEL_PATH)
        interp.allocate_tensors()
    except Exception as e:
        print(f"ERROR load model: {e}")
        with lock:
            jenis_sayuran = "Model Error"
        return

    inp_det = interp.get_input_details()[0]
    out_det = interp.get_output_details()[0]

    # Auto-detect input format (NCHW vs NHWC)
    in_shape = inp_det['shape']
    if in_shape[1] == 3:       # [1, 3, H, W] -> NCHW
        target_h, target_w = in_shape[2], in_shape[3]
        is_nchw = True
    else:                      # [1, H, W, 3] -> NHWC
        target_h, target_w = in_shape[1], in_shape[2]
        is_nchw = False

    print(f"[Kamera] Model input shape: {in_shape}, NCHW={is_nchw}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Kamera tidak terbuka!")
        with lock:
            jenis_sayuran = "Kamera Error"
        return

    while running:
        ret, frame = cap.read()
        if not ret:
            continue

        # FIXED: Convert BGR → RGB (OpenCV baca BGR, model training pakai RGB)
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (target_w, target_h))
        img = img.astype(np.float32) / 255.0

        if is_nchw:
            img = np.transpose(img, (2, 0, 1))  # HWC → CHW
            input_data = np.expand_dims(img, axis=0)
        else:
            input_data = np.expand_dims(img, axis=0)

        # Inference
        interp.set_tensor(inp_det['index'], input_data)
        interp.invoke()
        pred = interp.get_tensor(out_det['index'])

        # Postprocessing
        best_conf, best_cls = 0, -1

        if pred.ndim >= 3:
            detections = pred[0]  # [N, 6] atau [25200, 85]

            if detections.shape[1] == 6:
                # Format: [x1, y1, x2, y2, conf, cls] (dengan NMS/TF export)
                for det in detections:
                    conf = float(det[4])
                    cls_id = int(det[5])
                    if conf > CONF_THRESHOLD and conf > best_conf and 0 <= cls_id < len(CLASS_NAMES):
                        best_conf = conf
                        best_cls = cls_id

            elif detections.shape[1] >= 5:
                # Format YOLOv5 raw: [x, y, w, h, obj_conf, cls0, cls1, ...]
                for det in detections:
                    obj_conf = float(det[4])
                    if obj_conf < CONF_THRESHOLD:
                        continue
                    if len(det) > 5:
                        cls_probs = det[5:]
                        cls_id = int(np.argmax(cls_probs))
                        conf = obj_conf * float(cls_probs[cls_id])
                    else:
                        cls_id = 0
                        conf = obj_conf

                    if conf > CONF_THRESHOLD and conf > best_conf and 0 <= cls_id < len(CLASS_NAMES):
                        best_conf = conf
                        best_cls = cls_id

        with lock:
            if best_cls >= 0:
                jenis_sayuran = CLASS_NAMES[best_cls].capitalize()
            else:
                jenis_sayuran = "Tidak Terdeteksi"

        time.sleep(0.05)

    cap.release()
    print("[Kamera] Thread berhenti.")

# ================= KIRIM DATA =================
def kirim_data(berat_kg, jenis):
    url = (f"https://script.google.com/macros/s/"
           f"{GOOGLE_SCRIPT_ID}/exec"
           f"?berat={berat_kg:.2f}&jenis={jenis}")
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True)
        print(f"Terkirim: {berat_kg:.2f} Kg, {jenis}")
        return True
    except Exception as e:
        print(f"Gagal kirim: {e}")
        return False

# ================= MAIN =================
def main():
    global running

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # Init LCD
    lcd.clear()
    lcd_print(0, 0, "TIMBANGAN DIGITAL")
    lcd_print(1, 0, "INIT LOAD CELL..")

    # Init HX711
    init_hx711()

    lcd.clear()
    lcd_print(0, 0, "INIT KAMERA...")
    lcd_print(1, 0, "TUNGGU SEBENTAR")

    # Start camera thread
    cam_thread = threading.Thread(target=camera_detection_thread)
    cam_thread.daemon = True
    cam_thread.start()

    # Tunggu kamera & model siap
    time.sleep(2)

    last_btn = GPIO.HIGH
    t_update = 0
    t_display = 0

    lcd.clear()
    lcd_print(0, 0, "SISTEM SIAP!")
    lcd_print(1, 0, "TOMBOL=KIRIM")
    print("\nSistem siap! Tekan CTRL+C untuk keluar.\n")
    time.sleep(1)
    lcd.clear()

    try:
        while True:
            now = time.time()

            # Update berat tiap 10ms (sama dengan timbangan_fixed.py)
            if now - t_update >= 0.01:
                get_kg()
                t_update = now

            # Refresh LCD tiap 500ms (sama dengan timbangan_fixed.py)
            if now - t_display >= 0.5:
                with lock:
                    j = jenis_sayuran
                lcd_print(0, 0, f"BERAT:{kg:7.2f} KG ")
                lcd_print(1, 0, f"Sayur:{j[:10]:<10}")
                t_display = now

            # Cek tombol (deteksi turun HIGH→LOW)
            btn = GPIO.input(PIN_BUTTON)
            if btn == GPIO.LOW and last_btn == GPIO.HIGH:
                with lock:
                    j = jenis_sayuran
                print(f"\nTombol ditekan! {kg:.2f} Kg, {j}")
                lcd_clear_line(1)
                lcd_print(1, 0, "Mengirim... ")
                ok = kirim_data(kg, j)
                lcd_clear_line(1)
                lcd_print(1, 0, "Terkirim! " if ok else "Gagal Kirim! ")
                time.sleep(1.5)
                lcd_clear_line(1)

            last_btn = btn
            time.sleep(0.05)  # Debounce ~50ms

    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
        running = False
    finally:
        lcd.clear()
        lcd_print(0, 0, "SISTEM BERHENTI")
        time.sleep(1)
        lcd.close(clear=True)
        GPIO.cleanup()
        try:
            hx.power_down()
        except Exception:
            pass
        cam_thread.join(timeout=3)
        print("Selesai.")

if __name__ == "__main__":
    main()
