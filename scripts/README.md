## SOP (*Standar Operasional Prosedur*) alat 

1. Aktifkan **toggle switch** Power Supply sehingga Raspberry Pi CM4 booting dan otomatis menjalankan skrip serta layanan n8n.
3. Letakkan sayuran di atas platform timbangan (titik uji di tengah alas, area bertanda). Load cell membaca berat, webcam memindai jenis sayuran; jika objek tidak dikenali, sistem memindai ulang.

<img width="887" height="376" alt="titik-uji" src="https://github.com/user-attachments/assets/8e8f19a0-2aa3-4635-9c2e-1ac055704390" />

<p align="center">
  <img width="550" height="250" alt="Load Cell Berat Sayur" src="https://github.com/user-attachments/assets/a45ad6e0-3718-4462-b722-91ba75fed9d0" />
</p>

5. LCD 16×2 menampilkan hasil, misal `Berat: 6.93 KG` dan `Jenis: Tomat`; nilai berat terkunci otomatis saat stabil (`>> STABIL <<`).
6. Tekan **push button** untuk mengirim data, sehingga LCD menampilkan `Mengirim data.. / Mohon tunggu...`, lalu konfirmasi `TERKIRIM + FOTO!` setelah berat, jenis, dan foto tersimpan di Google Sheets & Drive.
7. Pantau stok jarak jauh via **chatbot WhatsApp**: ketik `LOGIN`, masukkan **PIN** (sesi aktif 60 menit), lalu tanyakan stok, total berat masuk, jenis sayur per hari, kalkulasi pendapatan, atau minta lampiran foto produk.
