#!/usr/bin/env bash
# =====================================================================
# check-secrets.sh — Pindai repositori dari rahasia yang tertinggal
# ---------------------------------------------------------------------
#   bash scripts/check-secrets.sh
#
# Jalankan SEBELUM setiap commit. Skrip ini juga dijalankan oleh CI.
# =====================================================================

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

FAIL=0
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo "🔍 Memindai rahasia di $(pwd)"
echo

# ── 1. Berkas yang tidak boleh ter-commit ────────────────────────────
echo "── Berkas rahasia ─────────────────────────────────────"
for pattern in ".env" "device/.env" "n8n/.env" "infra/raspberry-pi/.env" \
               "*.pem" "*.key" "credentials.json" "service-account*.json" \
               "token.json" "client_secret*.json"; do
  if git ls-files --error-unmatch "$pattern" >/dev/null 2>&1; then
    echo -e "  ${RED}✗${NC} Ter-commit: $pattern"
    FAIL=1
  fi
done
[ "$FAIL" -eq 0 ] && echo -e "  ${GREEN}✓${NC} Tidak ada berkas rahasia yang ter-commit"
echo

# ── 2. Pola rahasia di dalam isi berkas ──────────────────────────────
echo "── Pola rahasia ───────────────────────────────────────"

# Direktori & berkas yang dikecualikan: skrip pemindai memang memuat polanya.
EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=node_modules
  --exclude-dir=__pycache__
  --exclude-dir=.venv
  --exclude=check-secrets.sh
  --exclude=sanitize-workflow.py
  --exclude=validate-workflow.py
  --exclude=SECURITY-NOTES.md
)

scan() {
  local pattern="$1" label="$2"
  local hits
  hits=$(grep -rInE "$pattern" . "${EXCLUDES[@]}" 2>/dev/null)
  if [ -n "$hits" ]; then
    echo -e "  ${RED}✗${NC} $label:"
    echo "$hits" | sed 's/^/      /'
    FAIL=1
  fi
}

scan 'AKfycb[A-Za-z0-9_-]{30,}'   'Deployment ID Google Apps Script'
scan 'gsk_[A-Za-z0-9]{20,}'       'Groq API key'
scan 'sk-[A-Za-z0-9]{20,}'        'API key gaya OpenAI'
scan 'AIza[A-Za-z0-9_-]{30,}'     'Google API key'
scan 'ya29\.[A-Za-z0-9_-]+'       'Google OAuth token'
scan 'gh[pousr]_[A-Za-z0-9]{20,}' 'GitHub token'
scan 'BEGIN [A-Z ]*PRIVATE KEY'   'Private key'
scan '[0-9]{10,15}@(s\.whatsapp\.net|c\.us)' 'Nomor WhatsApp'
scan 'spreadsheets/(d/)?(?!YOUR_GOOGLE_SHEET_ID)[A-Za-z0-9_-]{30,}' 'ID spreadsheet asli'
scan '"instanceId"'               'instanceId n8n'

echo

# ── 3. Nilai contoh yang belum diganti ───────────────────────────────
echo "── Peringatan ─────────────────────────────────────────"
WARN=0

if grep -rIn "STOK_PIN=1212\|STOK_PIN=0000\|STOK_PIN=1234" . "${EXCLUDES[@]}" 2>/dev/null | grep -qv ".example"; then
  echo -e "  ${YELLOW}⚠${NC}  PIN lemah terdeteksi di berkas non-contoh"
  WARN=1
fi

if [ -f device/.env ] && git ls-files --error-unmatch device/.env >/dev/null 2>&1; then
  echo -e "  ${RED}✗${NC} device/.env terlacak Git!"
  FAIL=1
fi

[ "$WARN" -eq 0 ] && echo -e "  ${GREEN}✓${NC} Tidak ada peringatan"
echo

# ── Ringkasan ────────────────────────────────────────────────────────
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}✅ Bersih — aman untuk di-commit.${NC}"
  exit 0
fi

echo -e "${RED}❌ Rahasia terdeteksi. JANGAN commit.${NC}"
echo
echo "Bila rahasia sudah terlanjur masuk riwayat Git, menghapusnya di commit"
echo "baru TIDAK cukup — riwayat tetap menyimpannya. Anda perlu:"
echo "  1. Cabut/rotasi kredensial tersebut sekarang juga"
echo "  2. git filter-repo, atau mulai repositori baru"
echo
echo "Lihat docs/SECURITY-NOTES.md"
exit 1
