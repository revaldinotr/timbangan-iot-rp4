# Apps Script — Jembatan ke Google Sheets & Drive

Skrip ini menerima POST dari Raspberry Pi, menyimpan foto ke Google Drive, dan
menulis satu baris data ke Google Sheets.

---

## Pemasangan

### 1. Buat spreadsheet

Buat spreadsheet baru di [sheets.google.com](https://sheets.google.com).
Header dibuat otomatis oleh skrip pada pengiriman pertama:

```
Timestamps | Berat (Kg) | Jenis Sayur | Foto
```

### 2. Tempel skrip

**Extensions → Apps Script**, hapus isi bawaan, tempel seluruh isi
`pb_to_sheets.gs`, lalu simpan.

### 3. Aktifkan token bersama (sangat disarankan)

Buat token acak:

```bash
openssl rand -hex 24
```

**Project Settings → Script Properties → Add script property**

| Property | Value |
|---|---|
| `SHARED_TOKEN` | token yang baru dibuat |

Isi nilai yang **sama persis** pada `GAS_SHARED_TOKEN` di `device/.env`.

> Tanpa langkah ini, endpoint Anda dapat ditulisi siapa pun yang mengetahui URL-nya.
> Lihat [`../docs/SECURITY-NOTES.md`](../docs/SECURITY-NOTES.md).

### 4. Deploy

**Deploy → New deployment → Web app**

| Pengaturan | Nilai |
|---|---|
| Execute as | **Me** |
| Who has access | **Anyone** |

Salin **Deployment ID** dari URL hasil deploy:

```
https://script.google.com/macros/s/<INI_DEPLOYMENT_ID>/exec
```

Masukkan ke `GAS_SCRIPT_ID` di `device/.env`.

> "Anyone" memang diperlukan agar Raspberry Pi dapat mengirim tanpa alur OAuth.
> Token bersama pada langkah 3 yang menggantikan fungsi autentikasi.

### 5. Uji

Di editor Apps Script, jalankan fungsi `testScript()`. Google akan meminta izin
akses Drive dan Spreadsheet pada eksekusi pertama.

Periksa hasilnya: satu baris baru di sheet, dan satu berkas di folder Drive
`Captures Data Sayur`.

---

## Skema Payload

```json
{
  "berat":      "3.39",
  "jenis":      "tomat",
  "filename":   "capture_1747000000.jpg",
  "imageData":  "<base64 JPEG>",
  "folderName": "Captures Data Sayur",
  "token":      "<SHARED_TOKEN bila diaktifkan>"
}
```

Respons sukses:

```json
{
  "status":    "OK",
  "timestamp": "2026-05-16 23:21:05",
  "fileUrl":   "https://drive.google.com/file/d/.../view",
  "fileId":    "..."
}
```

Respons ditolak:

```json
{ "status": "ERROR", "message": "Unauthorized" }
```

---

## Endpoint GET (tanpa foto)

Berguna untuk pengujian cepat dari peramban atau `curl`:

```
GET .../exec?berat=1.50&jenis=tomat&token=<SHARED_TOKEN>
```

---

## Formula Kolom Foto

Skrip menyisipkan formula gabungan agar sel menampilkan thumbnail yang bisa diklik:

```
=HYPERLINK("https://drive.google.com/file/d/ID/view";
           IMAGE("https://drive.google.com/uc?export=download&id=ID";4;60;80))
```

Dua hal penting:

1. **Pemisah argumen titik koma (`;`)** — mengikuti locale Indonesia. Bila spreadsheet
   Anda memakai locale yang menuntut koma, ubah pemisahnya di `pb_to_sheets.gs`.
2. **URL berbeda untuk dua fungsi** — `HYPERLINK` memakai `/view` (halaman Drive),
   sedangkan `IMAGE` memakai `uc?export=download` (berkas langsung). URL `/view`
   tidak akan tampil sebagai gambar.

Workflow n8n membaca kolom ini dalam mode FORMULA untuk mengekstrak file ID.

---

## Kuota Google

| Batas | Nilai (akun gratis) |
|---|---|
| Waktu eksekusi | 6 menit per pemanggilan |
| Panggilan URL Fetch | 20.000 / hari |
| Penyimpanan Drive | 15 GB dibagi seluruh layanan |
| Waktu total runtime | 90 menit / hari |

Foto dikompresi pada kualitas JPEG 70 di sisi perangkat untuk menghemat kuota
unggah dan penyimpanan.

---

## Mengubah Nama Sheet

Default: sheet aktif. Untuk menargetkan tab tertentu:

```javascript
var SHEET_NAME = "Stok";
```
