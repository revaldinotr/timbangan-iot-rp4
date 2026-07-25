# Panduan Instalasi Lengkap

Perkiraan waktu: **30–45 menit** untuk pemasangan pertama.

---

## Langkah 1 — Siapkan n8n

### Opsi A: n8n Cloud (paling mudah)

Daftar di [n8n.io](https://n8n.io), buat workspace. Webhook otomatis punya URL publik.

### Opsi B: Self-host dengan Docker

```bash
git clone https://github.com/<username>/manajemen-stok-sayur-wa.git
cd manajemen-stok-sayur-wa
cp .env.example .env
```

Buat kunci enkripsi lebih dulu:

```bash
openssl rand -hex 32
```

Tempel hasilnya ke `N8N_ENCRYPTION_KEY` di `.env`, isi juga user & password basic auth,
lalu jalankan:

```bash
docker compose up -d
docker compose logs -f n8n
```

Buka `http://localhost:5678`.

> ⚠️ **Simpan `N8N_ENCRYPTION_KEY` di tempat aman.** Jika hilang, semua credential yang
> tersimpan tidak bisa dibuka kembali.

### Membuat webhook lokal bisa diakses publik

Fonnte perlu menjangkau n8n Anda dari internet:

```bash
# ngrok
ngrok http 5678

# atau cloudflared
cloudflared tunnel --url http://localhost:5678
```

Salin URL HTTPS yang muncul ke `WEBHOOK_URL` di `.env`, lalu `docker compose up -d`
ulang. URL harus berakhiran garis miring, mis. `https://abc123.ngrok.io/`.

---

## Langkah 2 — Google Sheets

1. Buat spreadsheet baru di [sheets.google.com](https://sheets.google.com)
2. Isi baris pertama dengan header: `Timestamps | Berat (Kg) | Jenis Sayur | Foto`
   (bisa impor `examples/sheet-template.csv`)
3. Salin ID dari URL:

```
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
                                       └──────── ini ID-nya ────────┘
```

Format kolom Foto dijelaskan di [SPREADSHEET.md](SPREADSHEET.md).

---

## Langkah 3 — Credential Google Sheets di n8n

1. n8n → **Credentials** → **Add Credential** → *Google Sheets OAuth2 API*
2. Ikuti wizard OAuth n8n (untuk self-host, Anda perlu membuat OAuth Client ID di
   [Google Cloud Console](https://console.cloud.google.com) dan mengaktifkan
   **Google Sheets API**)
3. Beri nama: `Google Sheets account`
4. Klik **Connect my account** dan izinkan akses

---

## Langkah 4 — Fonnte

1. Daftar di [fonnte.com](https://fonnte.com)
2. **Add Device** → pindai QR dengan WhatsApp yang akan jadi nomor bot
3. Salin **Token** device
4. Di n8n → **Add Credential** → *Header Auth*:
   - **Name**: `Authorization`
   - **Value**: token Fonnte Anda
   - Beri nama credential: `Header Auth account`

> Gunakan nomor WhatsApp **terpisah** untuk bot, bukan nomor pribadi Anda.

---

## Langkah 5 — Groq

1. Buat API key di [console.groq.com/keys](https://console.groq.com/keys)
2. n8n → **Add Credential** → *Groq API* → tempel key
3. Beri nama: `Groq account`

---

## Langkah 6 — Import & Konfigurasi Workflow

1. n8n → **Workflows** → **Import from File**
2. Pilih `workflows/manajemen-stok-sayur-wa-pin.n8n.json`
3. Perbaiki hal-hal berikut (workflow sengaja dikirim tanpa nilai spesifik):

| Node | Yang harus diubah |
|---|---|
| `Ambil Data Sheets` | Ganti `YOUR_GOOGLE_SHEET_ID` di URL; pilih credential Google Sheets |
| `Ambil Link Foto` | Sama seperti di atas |
| `Groq Chat Model` | Pilih credential Groq |
| `Balas Pesan Auth` | Pilih credential Header Auth |
| `Kirim ke WhatsApp` | Pilih credential Header Auth |
| `Balas Pesan Tidak Valid` | Pilih credential Header Auth |
| `Kirim Foto ke WhatsApp` | Pilih credential Header Auth |

---

## Langkah 7 — Set PIN

**Jangan** mengandalkan fallback `0000` di dalam kode.

**n8n Cloud:** Settings → Variables → tambahkan `STOK_PIN`

**Self-host:** isi `STOK_PIN` di `.env`, lalu `docker compose up -d`

Verifikasi bahwa node Code bisa membaca env — pastikan
`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (sudah diatur di `docker-compose.yml`).

---

## Langkah 8 — Aktifkan & Sambungkan Webhook

1. Aktifkan workflow (toggle **Active** kanan atas)
2. Buka node `WhatsApp Webhook` → salin **Production URL**
3. Fonnte → **Device** → tempel URL ke kolom **Webhook**
4. Simpan

---

## Langkah 9 — Uji Coba

Dari WhatsApp pribadi Anda, kirim ke nomor bot:

```
LOGIN
```

Harusnya dibalas permintaan PIN. Masukkan PIN, lalu coba tanya
`stok tomat berapa?`.

Jika tidak ada balasan, baca [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Checklist Pasca-Instalasi

- [ ] `STOK_PIN` diset lewat environment variable, minimal 6 digit
- [ ] Basic auth n8n aktif
- [ ] `N8N_ENCRYPTION_KEY` dicadangkan di tempat aman
- [ ] Webhook memakai HTTPS
- [ ] Spreadsheet tidak dibagikan publik
- [ ] Nomor bot terpisah dari nomor pribadi
- [ ] Alur login sudah diuji ujung-ke-ujung
