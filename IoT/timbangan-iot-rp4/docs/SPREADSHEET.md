# Format Spreadsheet

## Struktur Dasar

Baris pertama **wajib** header. Baris berikutnya adalah data.

| Timestamps | Berat (Kg) | Jenis Sayur | Foto |
|---|---|---|---|
| 2026-05-16 23:21 | 3.39 | Tomat | *(link/formula)* |
| 2026-05-17 06:10 | 5.11 | Wortel | *(link/formula)* |

Impor cepat: `examples/sheet-template.csv` → File → Import → Replace spreadsheet.

---

## Penamaan Kolom Fleksibel

Nama kolom dicocokkan secara longgar, jadi Anda tidak harus persis mengikuti contoh:

| Yang dicari sistem | Contoh nama yang cocok |
|---|---|
| mengandung `foto` | `Foto`, `foto barang`, `FOTO PRODUK` |
| mengandung `sayur` | `Jenis Sayur`, `sayuran`, `Nama Sayur` |
| mengandung `berat` atau `kg` | `Berat (Kg)`, `berat`, `Total KG` |
| mengandung `time`/`stamp`/`tanggal` | `Timestamps`, `Tanggal Masuk`, `waktu` |

Jika kolom foto tidak ditemukan, sistem memakai **kolom terakhir**.
Jika kolom waktu tidak ditemukan, sistem memakai **kolom pertama**.

---

## Kolom Foto

Sistem mengekstrak file ID Google Drive dari tiga format:

### Format 1 — HYPERLINK (disarankan)

```
=HYPERLINK("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view";"lihat foto")
```

### Format 2 — IMAGE (thumbnail tampil di sheet)

```
=IMAGE("https://drive.google.com/uc?export=view&id=1AbCdEfGhIjKlMnOp")
```

### Format 3 — URL polos

```
https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view
```

Kosongkan sel bila tidak ada foto — baris tetap muncul di data, hanya kolom Foto
tertulis `-`.

> Pastikan foto di Drive dapat diakses oleh penerima. Setel berbagi ke
> **"Anyone with the link — Viewer"** untuk folder foto (bukan untuk spreadsheet-nya).

---

## Penanganan Sel Kosong

Sistem tidak error pada data tidak lengkap:

| Kondisi | Tampil sebagai |
|---|---|
| Jenis sayur kosong | `(tanpa nama)` |
| Kolom lain kosong | `kosong` |
| Berat `0` atau kosong | Diabaikan / `(berat belum dicatat)` |
| Foto kosong | `-` |

---

## Contoh Data Realistis

| Timestamps | Berat (Kg) | Jenis Sayur | Foto |
|---|---|---|---|
| 2026-05-16 23:21 | 3.39 | Tomat | `=HYPERLINK("https://drive.google.com/file/d/ID1/view";"foto")` |
| 2026-05-17 06:10 | 5.11 | Wortel | `=HYPERLINK("https://drive.google.com/file/d/ID2/view";"foto")` |
| 2026-05-17 08:02 | 20.10 | Tomat | `=IMAGE("https://drive.google.com/uc?id=ID3")` |
| 2026-05-17 09:45 | 12.00 | Kangkung | *(kosong)* |
| 2026-05-17 11:30 | 7.25 | Bayam | `https://drive.google.com/file/d/ID4/view` |

Pertanyaan `stok tomat berapa?` akan menghasilkan dua entri Tomat beserta total
23,49 Kg.

---

## Mengisi Otomatis dari Google Form

Cara praktis untuk pedagang: buat Google Form dengan field Berat, Jenis Sayur, dan
Upload Foto. Sambungkan responsnya ke spreadsheet ini.

Perhatikan: kolom foto hasil Form berisi URL Drive polos — **format 3** di atas, dan
sudah didukung.

Pastikan urutan/nama kolom hasil Form tetap memenuhi aturan pencocokan di atas.

---

## Batas Ukuran

Seluruh isi sheet dikirim ke LLM pada setiap pertanyaan. Praktisnya:

| Jumlah baris | Status |
|---|---|
| < 100 | Ideal |
| 100–300 | Baik, prompt mulai besar |
| 300–500 | Masih jalan, respons melambat, biaya token naik |
| > 500 | Berisiko melebihi context window |

Untuk data historis besar, pisahkan sheet arsip dan biarkan `Sheet1` hanya berisi stok
aktif.
