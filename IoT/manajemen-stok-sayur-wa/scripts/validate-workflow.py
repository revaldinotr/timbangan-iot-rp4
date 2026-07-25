#!/usr/bin/env python3
"""
validate-workflow.py
====================
Memeriksa workflow n8n sebelum di-commit / di-merge.

Pemeriksaan:
  1. JSON valid dan memiliki struktur workflow n8n
  2. Tidak ada rahasia / data spesifik instance yang tertinggal
  3. Semua ID credential kosong
  4. Semua target koneksi menunjuk ke node yang benar-benar ada
  5. Referensi $('Nama Node') di dalam node Code cocok dengan nama node nyata

Pemakaian:
    python3 scripts/validate-workflow.py workflows/*.json
"""

import glob
import json
import re
import sys
from pathlib import Path

FORBIDDEN = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "Groq API key"),
    (re.compile(r"AIza[A-Za-z0-9_-]{30,}"), "Google API key"),
    (re.compile(r"ya29\.[A-Za-z0-9_-]+"), "Google OAuth token"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "Private key"),
    (re.compile(r"\b\d{10,15}@(?:s\.whatsapp\.net|c\.us)\b"), "Nomor WhatsApp"),
    (
        re.compile(r"spreadsheets/(?:d/)?(?!YOUR_GOOGLE_SHEET_ID)[A-Za-z0-9_-]{30,}"),
        "ID spreadsheet asli",
    ),
    (re.compile(r'"instanceId"'), "instanceId n8n"),
]

RE_NODE_REF = re.compile(r"\$\(\s*'([^']+)'\s*\)")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"JSON tidak valid: {exc}"]

    # --- 1. Struktur dasar ---------------------------------------------
    if "nodes" not in data or not isinstance(data["nodes"], list):
        errors.append("Tidak ada array 'nodes' — apakah ini benar workflow n8n?")
        return errors
    if "connections" not in data:
        errors.append("Tidak ada objek 'connections'")

    # --- 2. Rahasia ----------------------------------------------------
    for pattern, label in FORBIDDEN:
        if pattern.search(raw):
            errors.append(f"Rahasia terdeteksi: {label}")

    # --- 3. Credential harus kosong ------------------------------------
    for node in data["nodes"]:
        for cred_type, cred in (node.get("credentials") or {}).items():
            if isinstance(cred, dict) and cred.get("id"):
                errors.append(
                    f"Node '{node.get('name')}' masih memuat ID credential "
                    f"({cred_type}) — kosongkan sebelum commit"
                )

    # --- 4. Integritas koneksi -----------------------------------------
    names = {n.get("name") for n in data["nodes"]}
    for source, outputs in (data.get("connections") or {}).items():
        if source not in names:
            errors.append(f"Koneksi berasal dari node tidak dikenal: '{source}'")
        for branch in outputs.get("main", []) or []:
            for link in branch or []:
                target = link.get("node")
                if target not in names:
                    errors.append(
                        f"'{source}' terhubung ke node yang tidak ada: '{target}'"
                    )

    # --- 5. Referensi node di dalam kode --------------------------------
    for node in data["nodes"]:
        code = (node.get("parameters") or {}).get("jsCode") or ""
        for ref in set(RE_NODE_REF.findall(code)):
            if ref not in names:
                errors.append(
                    f"Node '{node.get('name')}' mereferensikan $('{ref}') "
                    f"yang tidak ada"
                )

    # --- Peringatan (tidak menggagalkan) --------------------------------
    if "YOUR_GOOGLE_SHEET_ID" not in raw:
        print("  ⚠️  Placeholder YOUR_GOOGLE_SHEET_ID tidak ditemukan — sengaja?")

    return errors


def main() -> int:
    args = sys.argv[1:] or ["workflows/*.json"]
    paths: list[Path] = []
    for arg in args:
        paths.extend(Path(p) for p in glob.glob(arg))

    if not paths:
        print("❌ Tidak ada berkas yang cocok.")
        return 1

    total = 0
    for path in paths:
        print(f"\n🔍 {path}")
        errors = validate(path)
        if errors:
            total += len(errors)
            for err in errors:
                print(f"  ❌ {err}")
        else:
            print("  ✅ Lolos semua pemeriksaan")

    print()
    if total:
        print(f"❌ Gagal: {total} masalah ditemukan.")
        return 1
    print("✅ Semua workflow lolos validasi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
