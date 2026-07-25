#!/usr/bin/env python3
"""
sanitize-workflow.py
====================
Membersihkan export workflow n8n dari data spesifik instance sebelum di-commit
ke repositori publik.

Yang dibersihkan:
  * ID Google Spreadsheet          -> YOUR_GOOGLE_SHEET_ID
  * ID credential internal n8n     -> "" (kosong)
  * webhookId & path webhook       -> "" (di-generate ulang saat import)
  * meta.instanceId, versionId, id -> dihapus
  * PIN fallback yang di-hardcode  -> 0000
  * Token panjang yang mencurigakan-> ditandai untuk ditinjau manual

Pemakaian:
    python3 scripts/sanitize-workflow.py masukan.json keluaran.json
    python3 scripts/sanitize-workflow.py masukan.json          # tulis di tempat (in-place)
"""

import json
import re
import sys
from pathlib import Path

PLACEHOLDER_SHEET = "YOUR_GOOGLE_SHEET_ID"
PLACEHOLDER_PIN = "0000"

# Pola ID Google Spreadsheet di dalam URL API/UI
RE_SHEET_URL = re.compile(r"(spreadsheets/(?:d/)?)([A-Za-z0-9_-]{30,})")

# PIN fallback di dalam node Code, mis.  : '1212';
RE_PIN_FALLBACK = re.compile(r"(?<=:\s')(\d{4,8})(?=';)")

# Token yang tidak boleh pernah masuk repo
RE_SUSPECT = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "Groq API key"),
    (re.compile(r"AIza[A-Za-z0-9_-]{30,}"), "Google API key"),
    (re.compile(r"ya29\.[A-Za-z0-9_-]+"), "Google OAuth access token"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\b\d{10,15}@(?:s\.whatsapp\.net|c\.us)\b"), "Nomor WhatsApp"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "Private key"),
]

found_secrets: list[str] = []
changes: list[str] = []


def scrub(text: str) -> str:
    original = text

    new = RE_SHEET_URL.sub(lambda m: m.group(1) + PLACEHOLDER_SHEET, text)
    if new != text:
        changes.append("ID spreadsheet diganti placeholder")
    text = new

    new = RE_PIN_FALLBACK.sub(PLACEHOLDER_PIN, text)
    if new != text:
        changes.append("PIN fallback diganti 0000")
    text = new

    # PIN yang ikut tertulis di catatan/notes node
    text = re.sub(r"(fallback\s+)\d{4,8}", r"\g<1>" + PLACEHOLDER_PIN, text)

    for pattern, label in RE_SUSPECT:
        if pattern.search(original):
            found_secrets.append(label)

    return text


def walk(node):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "credentials" and isinstance(value, dict):
                for cred in value.values():
                    if isinstance(cred, dict) and cred.get("id"):
                        cred["id"] = ""
                        changes.append("ID credential dikosongkan")
                continue
            if isinstance(value, str):
                node[key] = scrub(value)
            else:
                walk(value)
    elif isinstance(node, list):
        for item in node:
            walk(item)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src

    if not src.exists():
        print(f"❌ Berkas tidak ditemukan: {src}")
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    walk(data)

    # Buang metadata identitas instance
    for key in ("versionId", "id", "meta"):
        if data.pop(key, None) is not None:
            changes.append(f"{key} dihapus")

    # Reset webhook agar di-generate ulang saat import
    for node in data.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            node.setdefault("parameters", {})["path"] = ""
            node["webhookId"] = ""
            changes.append("path & webhookId direset")

    data.setdefault("pinData", {})

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"✅ Tersanitasi: {src}  →  {dst}\n")
    if changes:
        print("Perubahan yang dilakukan:")
        for item in sorted(set(changes)):
            print(f"  • {item} ({changes.count(item)}×)")

    if found_secrets:
        print("\n🚨 RAHASIA TERDETEKSI — periksa manual sebelum commit:")
        for item in sorted(set(found_secrets)):
            print(f"  • {item}")
        print("\nScript ini TIDAK menghapusnya otomatis. Cabut/rotasi token tersebut.")
        return 1

    print("\nTidak ada token mencurigakan yang terdeteksi.")
    print("Langkah berikutnya: python3 scripts/validate-workflow.py", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
