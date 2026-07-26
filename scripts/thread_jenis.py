#!/usr/bin/env python3
"""
Thread deteksi jenis sayur (YOLOv5 TFLite + webcam).
modul ini hanya membaca kamera, menjalankan inferensi, dan menulis
hasilnya ke shared state. Fungsi `capture_frame()` menyimpan foto beranotasi
ke disk secara LOKAL.

Uji mandiri:
    python scripts/thread_jenis.py
"""

import os
import sys
import time
from collections import deque
from typing import Optional

import numpy as np
import cv2

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.common import (
    # konfigurasi
    MODEL_PATH, CLASS_NAMES, CLASS_COLORS, CONF_THRESH, IOU_THRESH,
    INPUT_SIZE, NUM_THREADS, WEBCAM_INDEX, WEBCAM_WIDTH, WEBCAM_HEIGHT,
    CONFIRM_FRAMES, CAPTURE_DIR, JPEG_QUALITY,
    # runtime
    log, set_state, should_stop, request_stop, jenis_ready,
)

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
#  KAMERA
# ═══════════════════════════════════════════════════════════════════════════════
def open_camera():
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


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL & INFERENSI
# ═══════════════════════════════════════════════════════════════════════════════
def load_model(path):
    if not os.path.exists(path):
        log(f"Model tidak ditemukan: {path}", "WARN")
        log("Pastikan file .tflite ada di folder 'model/'.", "WARN")
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
        log(f"  Input TERKUANTISASI (scale={in_quant[0]}, zero={in_quant[1]}).")
    if out_dtype in ("uint8", "int8"):
        log(f"  Output TERKUANTISASI (scale={out_quant[0]}, zero={out_quant[1]}).")
    return interpreter, inp, outp


def preprocess(frame, inp_detail=None, size=INPUT_SIZE):
    """
    Letterbox frame → (size x size) lalu siapkan tensor sesuai dtype model.
      - FP32 / FP16 : float32 dinormalisasi 0..1
      - INT8 / UINT8: dikuantisasi pakai (scale, zero_point) dari model
    Catatan: model FP16 TFLite tetap menerima input float32 (bobotnya saja
    yang half-precision), jadi cabang float di bawah sudah benar.
    """
    h, w = frame.shape[:2]
    scale  = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(frame, (nw, nh))
    padded  = np.full((size, size, 3), 114, dtype=np.uint8)
    top  = (size - nh) // 2
    left = (size - nw) // 2
    padded[top:top + nh, left:left + nw] = resized
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)

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

    return np.expand_dims(img, 0), scale, left, top


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


# ═══════════════════════════════════════════════════════════════════════════════
#  CAPTURE FOTO LOKAL (overlay kotak + berat & jenis) → captures/
# ═══════════════════════════════════════════════════════════════════════════════
def capture_frame(frame, detections, berat_kg: float, jenis: str) -> Optional[str]:
    """
    Simpan foto + bounding box + overlay (berat & jenis) ke folder captures/.
    Murni operasi lokal — tidak ada upload di sini.
    Return path file, atau None bila gagal.
    """
    if frame is None:
        log("Tidak ada frame untuk di-capture.", "WARN")
        return None

    img = frame.copy()
    for (x1, y1, x2, y2, name, conf) in (detections or []):
        color = CLASS_COLORS.get(name, (255, 255, 0))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{name}: {conf:.2f}", (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    jenis_txt = jenis if (jenis and jenis != "...") else "-"
    cv2.putText(img, f"{berat_kg:.2f} kg | {jenis_txt}", (8, img.shape[0] - 10),
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
#  ENTRY POINT THREAD
# ═══════════════════════════════════════════════════════════════════════════════
def thread_jenis():
    """Loop kamera: baca → inferensi → update state jenis terkonfirmasi."""
    try:
        interpreter, inp_det, outp_det = load_model(MODEL_PATH)
    except SystemExit:
        log("Model gagal dimuat — menghentikan sistem.", "ERROR")
        request_stop()   # agar splash & main keluar bersih, tidak menggantung
        return

    log(f"Membuka webcam index {WEBCAM_INDEX}...")
    cap = open_camera()
    if cap is None:
        log("Tidak ada webcam terdeteksi! Cek: ls /dev/video*", "WARN")
        request_stop()
        return
    log("Webcam aktif. Mulai deteksi...")
    jenis_ready.set()   # model dimuat + kamera terbuka → komponen jenis siap

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

            # Log kecepatan inferensi sekali (gauge performa di RPi4).
            if not _timed_once:
                log(f"Inferensi pertama: {_t_inf*1000:.0f} ms "
                    f"(~{1.0/max(_t_inf, 1e-3):.1f} FPS inferensi murni). "
                    f"Capture {orig_w}x{orig_h}.")
                _timed_once = True

            # Dequantisasi output bila model terkuantisasi (FP32/FP16: dilewati).
            if np.dtype(outp_det['dtype']).name in ("uint8", "int8"):
                o_scale, o_zero = outp_det.get('quantization', (1.0, 0))
                if o_scale not in (0, 0.0):
                    output = (output.astype(np.float32) - o_zero) * o_scale

            detections = postprocess(output, scale, pad_left, pad_top, orig_h, orig_w)

            # Simpan frame & deteksi terakhir untuk capture saat tombol ditekan.
            set_state("last_frame", frame.copy())
            set_state("last_detections", detections)

            # Update history & konfirmasi jenis.
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
#  UJI MANDIRI — python3 scripts/thread_jenis.py
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import threading
    from scripts.common import get_state, request_stop

    t = threading.Thread(target=thread_jenis, name="Thread-Jenis", daemon=True)
    t.start()
    print("Uji mandiri deteksi jenis. CTRL+C untuk keluar.")

    try:
        while t.is_alive():
            time.sleep(0.5)
            print(f"\rJenis: {get_state('jenis'):<12}", end="")
    except KeyboardInterrupt:
        print()
    finally:
        request_stop()
        t.join(timeout=3.0)
