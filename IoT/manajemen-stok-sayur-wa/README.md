# 🥬 Manajemen Stok Sayur Pasar Tradisional

Bot WhatsApp berbasis **n8n** untuk mengelola dan menanyakan data stok sayur di pasar
tradisional. Pedagang cukup mengirim pesan WhatsApp biasa — bot menjawab dengan data
terkini dari Google Sheets, lengkap dengan link foto barang.

Dilindungi login berbasis **PIN** dengan sesi berbatas waktu, sehingga data stok tidak
bisa diakses sembarang nomor.

![n8n](https://img.shields.io/badge/n8n-workflow-EA4B71)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-beta-yellow)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

---

## 📑 Daftar Isi

- [Fitur](#-fitur)
- [Cara Kerja](#-cara-kerja)
- [Struktur Repositori](#-struktur-repositori)
- [Prasyarat](#-prasyarat)
- [Instalasi Cepat](#-instalasi-cepat)
- [Struktur Spreadsheet](#-struktur-spreadsheet)
- [Cara Pakai](#-cara-pakai)
- [Keamanan](#-keamanan)
- [Roadmap](#-roadmap)
- [Kontribusi](#-kontribusi)
- [Lisensi](#-lisensi)

---

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| 🔐 **Login PIN** | Ketik `LOGIN`, masukkan PIN. Sesi aktif 60 menit dengan *sliding session*. |
| 🧹 **Auto-pruning sesi** | Sesi kedaluwarsa dibersihkan otomatis agar static data tidak membengkak. |
| 📊 **Sinkron Google Sheets** | Data dibaca langsung dari spreadsheet — tanpa database terpisah. |
| 🤖 **Jawaban natural (LLM)** | Ditenagai Groq. Bertanya bebas: "stok tomat berapa?", "total berat hari ini?" |
| 📷 **Kirim link foto** | Bot mendeteksi permintaan foto dan mengirim link Google Drive terkait. |
| 📱 **Format ramah WhatsApp** | Tanpa tabel/markdown yang berantakan di layar HP. |
| 🔁 **Anti echo-loop** | Event dari device sendiri disaring agar bot tidak membalas dirinya sendiri. |
| ♻️ **Retry otomatis** | Semua panggilan HTTP retry 3× dan gagal dengan anggun. |

---

## 🔄 Cara Kerja

```
                 ┌─────────────────┐
   WhatsApp ────▶│  Fonnte Gateway │────▶ Webhook n8n
                 └─────────────────┘
                                            │
                                            ▼
                                   ┌────────────────┐
                                   │ Bukan Echo Bot?│  saring event device sendiri
                                   └────────┬───────┘
                                            ▼
                                   ┌────────────────┐
                                   │   Has Text?    │  pastikan pesan tidak kosong
                                   └────────┬───────┘
                                            ▼
                                   ┌────────────────────┐
                                   │ Cek Status Sesi PIN│  state machine login
                                   └────────┬───────────┘
                            belum login ◀───┴───▶ sudah login
                                   │                  │
                                   ▼                  ▼
                          Balas minta PIN    ┌──────────────────┐
                                             │ Ambil Data Sheets│
                                             │ Ambil Link Foto  │
                                             └────────┬─────────┘
                                                      ▼
                                             ┌──────────────────┐
                                             │   Format Data    │ tabel teks + photoMap
                                             └────────┬─────────┘
                                                      ▼
                                             ┌──────────────────┐
                                             │     AI Agent     │ Groq + memory 6 turn
                                             └────────┬─────────┘
                                                      ▼
                                             ┌──────────────────┐
                                             │ Sanitasi Output  │ ekstrak [[SEND_PHOTOS]]
                                             └────┬────────┬────┘
                                                  ▼        ▼
                                          Kirim teks   Kirim link foto
```

**State machine login** ada 4 kondisi: `NOT_LOGGED_IN` → `WAITING_PIN` →
`LOGIN_SUCCESS` / `WRONG_PIN` → `AUTHENTICATED`. Detail di
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 📁 Struktur Repositori

```
manajemen-stok-sayur-wa/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
├── .gitignore
├── .env.example                 ← template variabel; salin jadi .env
├── docker-compose.yml           ← self-host n8n (opsional)
│
├── workflows/
│   └── manajemen-stok-sayur-wa-pin.n8n.json   ← workflow siap import
│
├── docs/
│   ├── SETUP.md                 ← panduan instalasi lengkap
│   ├── ARCHITECTURE.md          ← penjelasan tiap node
│   ├── SPREADSHEET.md           ← format & contoh sheet
│   └── TROUBLESHOOTING.md       ← masalah umum & solusinya
│
├── examples/
│   ├── sheet-template.csv       ← template spreadsheet
│   └── webhook-payload.example.json  ← contoh payload Fonnte
│
├── scripts/
│   ├── sanitize-workflow.py     ← bersihkan export sebelum commit
│   └── validate-workflow.py     ← cek struktur & sisa rahasia
│
└── .github/
    ├── workflows/ci.yml         ← CI: validasi + pemindaian rahasia
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 📦 Prasyarat

| Kebutuhan | Keterangan |
|---|---|
| **n8n** | v1.40+ — [n8n Cloud](https://n8n.io) atau self-host |
| **Akun Fonnte** | [fonnte.com](https://fonnte.com) — gateway WhatsApp, ada paket gratis |
| **Google Account** | Untuk Google Sheets + Drive (penyimpanan foto) |
| **Groq API Key** | [console.groq.com](https://console.groq.com/keys) — gratis dengan kuota |
| **URL publik** | Webhook harus bisa diakses Fonnte. Untuk lokal pakai ngrok/cloudflared. |

> ℹ️ Paket **gratis Fonnte tidak mendukung pengiriman media**. Karena itu foto dikirim
> sebagai **link Google Drive**, bukan lampiran gambar.

---

## 🚀 Instalasi Cepat

### 1. Clone repositori

```bash
git clone https://github.com/<username>/manajemen-stok-sayur-wa.git
cd manajemen-stok-sayur-wa
cp .env.example .env
```

Isi `.env` dengan nilai Anda sendiri.

### 2. Siapkan Google Sheets

Buat spreadsheet dengan kolom sesuai [`examples/sheet-template.csv`](examples/sheet-template.csv),
lalu salin ID-nya dari URL:

```
https://docs.google.com/spreadsheets/d/<SALIN_BAGIAN_INI>/edit
```

### 3. Import workflow ke n8n

n8n → **Workflows** → **Import from File** → pilih
`workflows/manajemen-stok-sayur-wa-pin.n8n.json`

### 4. Pasang credential

Workflow sengaja dikirim **tanpa credential**. Buat tiga credential berikut di n8n,
lalu pilih di node yang sesuai:

| Credential n8n | Tipe | Dipakai node |
|---|---|---|
| Fonnte | **Header Auth** — Name: `Authorization`, Value: token Fonnte | semua node `Kirim`/`Balas` |
| Google Sheets | **Google Sheets OAuth2 API** | `Ambil Data Sheets`, `Ambil Link Foto` |
| Groq | **Groq API** | `Groq Chat Model` |

### 5. Isi Sheet ID & PIN

- Ganti `YOUR_GOOGLE_SHEET_ID` di node **Ambil Data Sheets** dan **Ambil Link Foto**.
- Set environment variable `STOK_PIN` di instance n8n Anda.
  ⚠️ Jangan mengandalkan nilai fallback `0000` di dalam kode.

### 6. Aktifkan & sambungkan webhook

Aktifkan workflow, salin **Production URL** dari node `WhatsApp Webhook`, lalu tempel
ke Fonnte → **Device** → **Webhook URL**.

### 7. Uji coba

Kirim `LOGIN` ke nomor bot dari WhatsApp Anda. 🎉

Panduan lebih detail: [`docs/SETUP.md`](docs/SETUP.md)

---

## 📋 Struktur Spreadsheet

Baris pertama **wajib** berisi header. Nama kolom dideteksi secara longgar
(*case-insensitive*, cocok sebagian), jadi "Berat (Kg)" dan "berat kg" sama-sama dikenali.

| Timestamps | Berat (Kg) | Jenis Sayur | Foto |
|---|---|---|---|
| 2026-05-16 23:21 | 3.39 | Tomat | `=HYPERLINK("https://drive.google.com/file/d/ABC.../view";"lihat")` |
| 2026-05-17 06:10 | 5.11 | Wortel | `=IMAGE("https://drive.google.com/uc?id=XYZ...")` |

- **ID** dibuat otomatis dari nomor baris — tidak perlu kolom sendiri.
- Kolom **Foto** boleh berisi formula `HYPERLINK` atau `IMAGE`; keduanya diurai otomatis.
- Sel kosong ditampilkan sebagai `kosong` atau `(tanpa nama)`, tidak menyebabkan error.

Detail: [`docs/SPREADSHEET.md`](docs/SPREADSHEET.md)

---

## 💬 Cara Pakai

```
User  : LOGIN
Bot   : 🔒 Silakan masukkan PIN Anda untuk mengakses data:

User  : 123456
Bot   : ✅ Login berhasil!
        Selamat datang di Asisten Stok Sayur 🥬
        Sesi Anda aktif selama 60 menit.

User  : stok tomat berapa?
Bot   : Stok tomat saat ini ada 2 entri:
        - *Tomat* — 3,39 Kg · 2026-05-16 23:21 · ID 5
        - *Tomat* — 20,1 Kg · 2026-05-17 08:02 · ID 9

        Total: Tomat 23,49 Kg (2 entri)

User  : kirim foto tomat
Bot   : 📷 Link foto yang diminta:
        1. Tomat (3,39 Kg) — 2026-05-16 23:21
           https://drive.google.com/file/d/.../view
```

Perintah lain yang dipahami: total berat, entri terberat, data per tanggal, rekap per
jenis sayur — bebas dalam bahasa natural.

---

## 🔒 Keamanan

Beberapa hal yang **wajib** diperhatikan sebelum dipakai sungguhan:

- **PIN lewat environment variable.** Fallback `0000` di kode hanya untuk demo. Set
  `STOK_PIN` di n8n dan gunakan minimal 6 digit.
- **Jangan commit export mentah.** Export n8n memuat ID spreadsheet, path webhook, dan
  ID credential. Jalankan dulu:
  ```bash
  python3 scripts/sanitize-workflow.py workflow.raw.json workflows/output.json
  ```
- **PIN tunggal untuk semua user.** Ini keterbatasan desain saat ini. Untuk multi-user
  dengan hak akses berbeda, lihat [Roadmap](#-roadmap).
- **Batasi akses spreadsheet.** Jangan set "siapa saja yang punya link" jika berisi data
  usaha yang sensitif.
- **Rate limiting belum ada.** PIN bisa ditebak berulang kali. Kontribusi untuk
  lockout/throttling sangat diterima.

Menemukan celah keamanan? Baca [`SECURITY.md`](SECURITY.md) — jangan buka issue publik.

---

## 🗺️ Roadmap

- [ ] PIN per-nomor (multi-user) dengan level akses
- [ ] Rate limiting & lockout setelah N kali PIN salah
- [ ] Input data lewat WhatsApp (tambah/ubah stok, bukan hanya baca)
- [ ] Kirim foto sebagai media asli (paket Fonnte berbayar)
- [ ] Notifikasi otomatis stok menipis
- [ ] Laporan harian/mingguan terjadwal
- [ ] Dukungan gateway alternatif (Twilio, WhatsApp Cloud API)
- [ ] Migrasi sesi dari static data ke Redis
- [ ] Pencatatan audit log

---

## 🤝 Kontribusi

Kontribusi sangat terbuka! Baca [`CONTRIBUTING.md`](CONTRIBUTING.md) untuk alur kerja,
konvensi commit, dan **wajib**: sanitasi workflow sebelum PR.

Singkatnya:

```bash
git checkout -b fitur/nama-fitur
# ... ubah workflow di n8n, export ...
python3 scripts/sanitize-workflow.py export-mentah.json workflows/manajemen-stok-sayur-wa-pin.n8n.json
python3 scripts/validate-workflow.py workflows/manajemen-stok-sayur-wa-pin.n8n.json
git commit -m "feat: tambahkan X"
```

---

## 📄 Lisensi

[MIT](LICENSE) — bebas dipakai, diubah, dan didistribusikan.

## 🙏 Terima Kasih

Dibangun dengan [n8n](https://n8n.io), [Fonnte](https://fonnte.com),
[Groq](https://groq.com), dan Google Sheets.

---

<sub>Dibuat untuk membantu pedagang pasar tradisional mengelola stok dengan alat yang
sudah mereka punya: WhatsApp.</sub>
