# Catatan Keamanan

Dokumen ini menjelaskan risiko nyata pada sistem ini dan cara menutupnya.
**Baca sebelum menjalankan di lingkungan produksi.**

---

## 🚨 1. Endpoint Apps Script adalah endpoint tulis publik

Ini risiko paling serius pada arsitektur ini.

Web app Apps Script harus di-deploy dengan **Execute as: Me** dan
**Who has access: Anyone** agar Raspberry Pi bisa mengirim data tanpa alur OAuth.
Konsekuensinya:

> Siapa pun yang mengetahui URL `/exec` dapat menyisipkan baris ke Spreadsheet Anda
> dan mengunggah berkas apa pun ke Google Drive Anda — tanpa login, tanpa jejak
> identitas.

Deployment ID **bukan** sekadar pengenal; ia berfungsi seperti kata sandi.

### Dampak bila bocor

| Serangan | Akibat |
|---|---|
| Injeksi data | Data stok dipenuhi baris palsu |
| Pengurasan kuota Drive | Penyerang mengunggah berkas besar berulang kali |
| Penyalahgunaan penyimpanan | Drive Anda dipakai menampung konten pihak lain |
| Peracunan data chatbot | AI menjawab berdasarkan data yang sudah dimanipulasi |

### Cara menutupnya

**Langkah 1 — Aktifkan token bersama**

Buat token acak:

```bash
openssl rand -hex 24
```

Di editor Apps Script: **Project Settings → Script Properties → Add script property**

| Property | Value |
|---|---|
| `SHARED_TOKEN` | hasil perintah di atas |

Di `device/.env`:

```
GAS_SHARED_TOKEN=hasil-yang-sama-persis
```

Setelah aktif, permintaan tanpa token yang benar akan ditolak dengan
`{"status":"ERROR","message":"Unauthorized"}`.

**Langkah 2 — Ganti Deployment ID bila pernah bocor**

Deployment ID lama tidak bisa "dicabut" nilainya, tetapi deployment-nya bisa
dihentikan:

1. Apps Script → **Deploy → Manage deployments**
2. Arsipkan/hapus deployment lama
3. Buat **New deployment** → dapat Deployment ID baru
4. Perbarui `GAS_SCRIPT_ID` di `device/.env`

> ⚠️ **Bila Anda pernah meng-commit `main.py` yang memuat Deployment ID asli
> ke repositori publik, anggap ID tersebut sudah tersebar.** Menghapusnya di
> commit baru tidak cukup — riwayat Git tetap menyimpannya, dan bot pemindai
> GitHub bekerja dalam hitungan menit. Buat deployment baru.

**Langkah 3 — Batasi folder Drive**

Skrip memanggil `setSharing(ANYONE_WITH_LINK, VIEW)` pada setiap foto agar bisa
tampil di Sheets dan dibuka lewat WhatsApp. Artinya foto memang dapat diakses siapa
pun yang memegang link-nya. Jangan menyimpan apa pun yang sensitif di folder ini.

---

## 🔐 2. PIN chatbot bersifat tunggal

Satu PIN berlaku untuk semua nomor WhatsApp. Tidak ada pemisahan hak akses, tidak ada
pembatasan jumlah percobaan.

**Mitigasi saat ini:**

- Gunakan PIN minimal 6 digit — hindari `1234`, `0000`, tanggal lahir
- Set lewat environment variable `STOK_PIN`, jangan andalkan nilai fallback di kode
- Ganti PIN secara berkala
- Perpendek `SESSION_MINUTES` bila perangkat dipakai bergantian

Rate limiting ada di roadmap; kontribusi diterima.

---

## 🔑 3. Rahasia yang tidak boleh masuk Git

| Rahasia | Tempat yang benar |
|---|---|
| Deployment ID Apps Script | `device/.env` |
| Token bersama | `device/.env` + Script Properties |
| PIN chatbot | environment variable n8n |
| Token Fonnte | credential n8n |
| API key Groq | credential n8n |
| Token Cloudflare Tunnel | `infra/raspberry-pi/.env` |
| Kunci enkripsi n8n | `infra/raspberry-pi/.env` |
| ID Spreadsheet | placeholder di repo, isi saat import |

Semua sudah tercakup `.gitignore`. Verifikasi sebelum push:

```bash
bash scripts/check-secrets.sh
```

---

## 🔁 4. Sanitasi export n8n

Export workflow n8n **selalu** memuat data spesifik instance: ID spreadsheet, path
webhook, ID credential, dan `instanceId`. Wajib dibersihkan:

```bash
python3 scripts/sanitize-workflow.py export-mentah.json n8n/workflows/keluaran.json
python3 scripts/validate-workflow.py n8n/workflows/keluaran.json
```

---

## 🌐 5. Keamanan jaringan

- **Selalu HTTPS** untuk webhook n8n. Cloudflare Tunnel menyediakannya otomatis.
- **Aktifkan basic auth** pada panel n8n — panel yang terbuka berarti seluruh
  credential Anda terbuka.
- **Jangan port-forward** port 5678 langsung ke internet. Pakai tunnel.
- **Cadangkan `N8N_ENCRYPTION_KEY`.** Tanpa kunci ini, seluruh credential tersimpan
  tidak dapat dipulihkan.

---

## 📋 Checklist Sebelum Produksi

- [ ] `SHARED_TOKEN` aktif di Apps Script dan cocok dengan `device/.env`
- [ ] Deployment ID baru dibuat bila ID lama pernah tersebar
- [ ] `STOK_PIN` minimal 6 digit, diset lewat environment variable
- [ ] Basic auth n8n aktif
- [ ] `N8N_ENCRYPTION_KEY` dicadangkan di luar perangkat
- [ ] Webhook memakai HTTPS
- [ ] `bash scripts/check-secrets.sh` bersih
- [ ] Spreadsheet tidak dibagikan publik
- [ ] Folder Drive tidak berisi data sensitif
- [ ] Nomor WhatsApp bot terpisah dari nomor pribadi

---

## 📨 Melaporkan Kerentanan

Jangan buka issue publik. Kirim ke `<email-keamanan-anda>`.
Lihat [`../SECURITY.md`](../SECURITY.md).
