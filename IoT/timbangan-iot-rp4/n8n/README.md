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

# Pemecahan Masalah

## Bot tidak membalas sama sekali

**1. Cek workflow aktif.** Toggle **Active** di kanan atas harus menyala. Webhook test
hanya hidup 120 detik setelah klik "Listen".

**2. Cek URL webhook di Fonnte.** Harus **Production URL**, bukan Test URL. Salin ulang
dari node `WhatsApp Webhook`.

**3. Cek device Fonnte terhubung.** Panel Fonnte → status device harus `connected`.
Jika `disconnected`, pindai ulang QR.

**4. Lihat riwayat eksekusi.** n8n → **Executions**. Jika kosong, webhook tidak pernah
menerima apa pun — masalah ada di sisi Fonnte atau jaringan.

**5. Self-host: cek `WEBHOOK_URL`.** Bila salah, n8n menampilkan URL yang tidak bisa
dijangkau dari luar. Harus URL publik dan diakhiri garis miring.

---
## Error 429 / rate limit

**Dari Groq:** kuota gratis habis. Tunggu reset atau upgrade.
**Dari Fonnte:** melebihi batas pesan paket Anda.

Kedua node HTTP sudah retry 3×, tapi retry tidak menolong bila kuota memang habis.

---

## Error 401 / 403

Credential bermasalah:

| Layanan | Penyebab umum |
|---|---|
| Fonnte | Token salah, atau header bukan `Authorization` |
| Google | OAuth kedaluwarsa/dicabut, atau API belum aktif |
| Groq | API key salah atau sudah dihapus |

---

## Masih bermasalah?

- Screenshot riwayat eksekusi n8n (**sensor token & nomor telepon**)
- Versi n8n
- Cloud atau self-host

⚠️ **Jangan tempel token, API key, atau nomor WhatsApp** ke dalam issue publik.


