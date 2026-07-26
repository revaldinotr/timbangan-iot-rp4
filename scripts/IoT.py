#!/usr/bin/env python3
"""
Bagian pengiriman data & foto ke cloud (Google Apps Script).

Endpoint & folder Drive dibaca dari scripts/common.py, yang mengambilnya dari
environment variable / file .env. Kalau GOOGLE_SHEETS_SCRIPT_ID belum diisi,
fungsi kirim menolak dengan pesan.

Uji mandiri:
    python scripts/IoT.py                      # kirim data uji tanpa foto
    python scripts/IoT.py foto.jpg 1.25 tomat  # kirim dengan foto
"""

import os
import sys
import base64
from typing import Optional, Tuple

import requests

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.common import (
    GOOGLE_SHEETS_URL, GOOGLE_DRIVE_FOLDER_NAME, UPLOAD_TIMEOUT,
    iot_enabled, log,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENCODE FOTO → BASE64
# ═══════════════════════════════════════════════════════════════════════════════
def encode_image(image_path: Optional[str]) -> Tuple[str, str]:
    """Return (base64_string, filename). Keduanya "" bila tidak ada / gagal."""
    if not image_path or not os.path.exists(image_path):
        return "", ""
    try:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
        filename = os.path.basename(image_path)
        log(f"Foto dikodekan: {filename} ({len(image_b64) // 1024} KB base64)")
        return image_b64, filename
    except Exception as ex:
        log(f"Gagal encode foto: {ex}", "WARN")
        return "", ""


# ═══════════════════════════════════════════════════════════════════════════════
#  KIRIM DATA GABUNGAN (berat + jenis + foto)
# ═══════════════════════════════════════════════════════════════════════════════
def kirim_semua(
    berat_kg: float, jenis_str: str, image_path: Optional[str]
) -> Tuple[bool, str]:
    """
    Kirim SATU baris gabungan: berat + jenis + foto dalam SATU POST request.
    Skema payload 5-kunci identik dengan sistem awal → endpoint GAS kompatibel.
    GAS membalas redirect 302 → diikuti GET untuk mengambil body JSON.

    Return (sukses, foto_url).
    """
    if not iot_enabled():
        log("IoT nonaktif — GOOGLE_SHEETS_SCRIPT_ID belum diisi di .env", "WARN")
        return False, ""

    jenis_kirim = (
        jenis_str.split(",")[0].strip() if jenis_str and jenis_str != "..." else ""
    )
    image_b64, filename = encode_image(image_path)

    payload = {
        "berat"     : f"{berat_kg:.2f}",
        "jenis"     : jenis_kirim,
        "filename"  : filename,
        "imageData" : image_b64,
        "folderName": GOOGLE_DRIVE_FOLDER_NAME,
    }

    log(
        f"Kirim → berat={berat_kg:.2f}kg | jenis={jenis_kirim or '-'}"
        + (f" | foto={filename}" if filename else " | foto=tidak ada")
    )

    try:
        resp = requests.post(
            GOOGLE_SHEETS_URL,
            json=payload,
            allow_redirects=False,
            timeout=UPLOAD_TIMEOUT,
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
                log(f"✗ GAS error: {data.get('message', '?')}", "WARN")
                return False, ""
            except Exception:
                log("✓ Berhasil (response non-JSON diabaikan)")
                return True, ""

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
#  UJI MANDIRI — python3 scripts/IoT.py [foto.jpg] [berat] [jenis]
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not iot_enabled():
        print("GOOGLE_SHEETS_SCRIPT_ID belum di-set.")
        print("Jalankan:  cp .env.example .env  lalu isi Script ID-nya.")
        sys.exit(1)

    foto  = sys.argv[1] if len(sys.argv) > 1 else None
    berat = float(sys.argv[2]) if len(sys.argv) > 2 else 1.23
    jenis = sys.argv[3] if len(sys.argv) > 3 else "tomat"

    sukses, url = kirim_semua(berat, jenis, foto)
    print(f"\nHasil: {'BERHASIL' if sukses else 'GAGAL'}"
          + (f" | URL foto: {url}" if url else ""))
