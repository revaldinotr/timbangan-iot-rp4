# Chatbot WhatsApp (n8n)

Workflow n8n yang memungkinkan pedagang menanyakan data stok lewat WhatsApp.

---

## Import

n8n → **Workflows** → **Import from File** → pilih
`workflows/manajemen-stok-sayur-wa-pin.n8n.json`

Workflow sengaja dikirim **tanpa credential dan tanpa ID spreadsheet** —
semuanya harus diisi setelah import.

## Yang Harus Diisi

| Node | Yang diubah |
|---|---|
| `Ambil Data Sheets` | Ganti `YOUR_GOOGLE_SHEET_ID`; pilih credential Google Sheets |
| `Ambil Link Foto` | Sama seperti di atas |
| `Groq Chat Model` | Pilih credential Groq |
| `Balas Pesan Auth` | Pilih credential Header Auth (Fonnte) |
| `Kirim ke WhatsApp` | Pilih credential Header Auth |
| `Balas Pesan Tidak Valid` | Pilih credential Header Auth |
| `Kirim Foto ke WhatsApp` | Pilih credential Header Auth |

## Credential yang Dibutuhkan

| Nama | Tipe | Sumber |
|---|---|---|
| Google Sheets account | Google Sheets OAuth2 API | Google Cloud Console |
| Header Auth account | Header Auth — Name `Authorization`, Value token | [fonnte.com](https://fonnte.com) |
| Groq account | Groq API | [console.groq.com/keys](https://console.groq.com/keys) |

## Set PIN

```
STOK_PIN=<minimal 6 digit>
```

**n8n Cloud:** Settings → Variables
**Self-host:** isi di `.env`, pastikan `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`

Jangan mengandalkan nilai fallback `0000` di dalam kode.

## Sambungkan Webhook

Aktifkan workflow → salin **Production URL** dari node `WhatsApp Webhook` →
tempel ke Fonnte → **Device** → **Webhook URL**.

---

## Menjalankan n8n Terpisah

Bila n8n dijalankan di mesin lain (bukan Raspberry Pi yang sama):

```bash
cp ../infra/raspberry-pi/.env.example .env
nano .env
docker compose up -d
```

Untuk pemasangan di Raspberry Pi bersama Cloudflare Tunnel, gunakan
[`../infra/raspberry-pi/`](../infra/raspberry-pi/).

---

## Sebelum Commit Perubahan Workflow

Export n8n memuat data spesifik instance Anda. **Wajib** disanitasi:

```bash
python3 ../scripts/sanitize-workflow.py export-mentah.json workflows/manajemen-stok-sayur-wa-pin.n8n.json
python3 ../scripts/validate-workflow.py workflows/manajemen-stok-sayur-wa-pin.n8n.json
```

---

## Dokumentasi Terkait

- Penjelasan tiap node → [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
- Format spreadsheet → [`../docs/SPREADSHEET.md`](../docs/SPREADSHEET.md)
- Masalah umum → [`../docs/TROUBLESHOOTING-CHATBOT.md`](../docs/TROUBLESHOOTING-CHATBOT.md)
