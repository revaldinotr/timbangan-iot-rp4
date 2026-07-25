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

### 3. Deploy

**Deploy → New deployment → Web app**

| Pengaturan | Nilai |
|---|---|
| Execute as | **Me** |
| Who has access | **Anyone** |

Salin **Deployment ID** dari URL hasil deploy:

```
https://script.google.com/macros/s/<INI_DEPLOYMENT_ID>/exec
```

> "Anyone" memang diperlukan agar Raspberry Pi dapat mengirim tanpa alur OAuth.
> Masukan Deployment ID ke script main.py di perangkat Raspberry pi.

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
