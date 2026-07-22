## Dokumentasi Pengujian & Hasil

### 1. Kalibrasi Load Cell
| Parameter | Nilai |
|---|---:|
| Nilai ADC tanpa beban (tare) | 392.468 |
| Nilai ADC beban acuan | 416.653 |
| Selisih nilai ADC (N benda - N tare) | 24.185 |
| Sensitivitas Aktual | 2,0272 mV/V |
| Massa beban acuan | 1.000 gram (1,00 kg) |
| Faktor kalibrasi (k) | 24,1850 |

![Terminal Hasil Kalibrasi](docs/images/hasil/terminal-kalibrasi.png)

### 2. Uji Akurasi & Presisi (7 beban × 10 pengulangan)

| Ref (kg) | Mean (kg) | Error (%) | Std (kg) | RSD (%) | Akurasi (%) |
|---:|---:|---:|---:|---:|---:|
| 1,00 | 1,00 | 0,50 | 0,0053 | 0,52 | 99,50 |
| 5,00 | 5,01 | 0,12 | 0,0052 | 0,10 | 99,88 |
| 10,00 | 10,01 | 0,09 | 0,0032 | 0,03 | 99,91 |
| 15,00 | 14,99 | 0,05 | 0,0048 | 0,03 | 99,95 |
| 20,00 | 20,01 | 0,05 | 0,0057 | 0,03 | 99,95 |
| 25,00 | 25,01 | 0,04 | 0,0057 | 0,02 | 99,96 |
| 30,00 | 30,01 | 0,02 | 0,0165 | 0,05 | 99,98 |

![Grafik Akurasi vs Beban](docs/images/hasil/grafik-akurasi.png)
![Grafik Error dan RSD](docs/images/hasil/grafik-error-rsd.png)

### 3. Uji Stabilitas (beban konstan 5–30 menit)
Drift maksimum 0,01–0,02 kg, tanpa pergeseran permanen (*no permanent drift / creep*); RSD 0,0229%–0,4816%; akurasi 99,70%–99,99%.

![Grafik Drift terhadap Waktu](docs/images/hasil/grafik-drift.jpeg)
![Grafik RSD Uji Stabilitas](docs/images/hasil/grafik-rsd-stabilitas.png)

### 4. Pelatihan & Deteksi YOLOv5n
Dataset 1.668 gambar (kentang 575, tomat 684, wortel 409), 200 epoch, evaluasi pada 167 gambar validasi:

| Kelas | Precision | Recall | mAP50 |
|---|---:|---:|---:|
| Kentang | 74,3% | 79,1% | 83,7% |
| Tomat | 93,2% | 97,7% | 98,3% |
| Wortel | 73,8% | 69,9% | 72,1% |
| **Keseluruhan** | **80,4%** | **82,2%** | **84,7%** |

Deteksi *real-time* (TFLite FP16 di CM4): **48/60 percobaan berhasil (80%)**, confidence rata-rata 80,6%, kecepatan **10-20 FPS** — tomat 90%, kentang 80%, wortel 70%.

<p align="center">
  <img src="docs/images/hasil/confusion-matrix.png" alt="Confusion Matrix">
</p>
<p align="center">
  <img src="docs/images/hasil/deteksi-realtime.jpeg" alt="Hasil Deteksi Real-time">
</p>


### 5. Integrasi Cloud & Chatbot
Pengujian dilakukan dengan menempatkan sampel sayuran di atas timbangan, menunggu LCD menampilkan pembacaan yang stabil, lalu menekan tombol pengiriman. Alur tampilan LCD berlangsung tiga tahap: kondisi awal (`Berat: 6.93 KG` / `Jenis: Tomat`) → status unggah (`Mengirim data.. / Mohon tunggu...`) saat berat, jenis, dan foto tangkapan kamera diunggah ke Google Apps Script → konfirmasi berhasil (`TERKIRIM + FOTO! 6.9kg Tomat`). Hasil: **13/15 percobaan berhasil** (waktu kirim 2–6 detik; kegagalan hanya terjadi saat Wi-Fi terputus/tidak stabil).

| Tampilan LCD (Berat & Jenis) | Proses Pengiriman | Berhasil Terkirim |
|:---:|:---:|:---:|
| ![LCD Berat dan Jenis](docs/images/hasil/lcd-berat-jenis.jpeg) | ![LCD Mengirim Data](docs/images/hasil/lcd-mengirim.jpeg) | ![LCD Terkirim + Foto](docs/images/hasil/lcd-terkirim.jpeg) |

![Antarmuka Pencatatan Google Sheets](docs/images/hasil/google-sheets.png)

Data stok sayur di Google Sheets diakses otomatis oleh workflow n8n melalui Google Sheets API setiap kali pengguna mengirim pertanyaan ke chatbot WhatsApp, sehingga jawaban LLM selalu berdasarkan kondisi stok terkini. Antarmuka workflow n8n ini dirancang dengan mengintegrasikan Fonnte API, webhook n8n, Google Sheets, autentikasi PIN, dan Groq LLaMA 3.3 70B.

![Desain Workflow n8n Chatbot WhatsApp](docs/images/hasil/n8n-workflow.png)

Saat Raspberry Pi baru terhubung ke daya dan Wi-Fi, sistem menjalani proses inisialisasi yang mencakup *booting* OS, *starting* *Docker container* n8n, hingga pembentukan koneksi Cloudflare Tunnel, dengan total *delay* sekitar ±2 menit sebelum sistem siap digunakan. Kondisi ini terkonfirmasi pada pengujian, di mana pesan yang dikirim pukul 9.18 pm dan 9.19 pm baru mendapatkan respons pada pukul 9.20 pm. Respons yang muncul kemudian menampilkan alur autentikasi PIN secara lengkap, mulai dari notifikasi bahwa pengguna belum *login*, instruksi untuk mengetik `LOGIN`, permintaan PIN, hingga konfirmasi *login* berhasil dengan sesi aktif selama 60 menit.

<p align="center">
  <img src="docs/images/hasil/chatbot-booting.jpeg" alt="Tangkapan Layar Chatbot WhatsApp Awal Booting">
</p>

*Chatbot* yang dikembangkan mampu:
- menjawab ketersediaan stok sayur secara *real-time*, lengkap dengan detail berat dan *timestamp* pencatatan;
- memahami pertanyaan lanjutan, seperti menghitung total berat masuk, mengidentifikasi jenis sayur pada hari tertentu, hingga mengkalkulasi potensi pendapatan ketika pengguna menyertakan harga jual;
- menjaga batas data dengan menjawab secara jujur ketika pertanyaan berada di luar cakupan *spreadsheet* (misalnya harga beli atau keuntungan), sembari menawarkan alternatif perhitungan yang relevan;
- mengirim foto produk dari Google Drive beserta daftar stok lengkap ketika diminta oleh pengguna.

| Uji Respons #1 | Uji Respons #2 | Uji Respons #3 |
|:---:|:---:|:---:|
| ![Uji Chatbot 1](docs/images/hasil/chatbot-uji-1.jpeg) | ![Uji Chatbot 2](docs/images/hasil/chatbot-uji-2.jpeg) | ![Uji Chatbot 3](docs/images/hasil/chatbot-uji-3.jpeg) |

