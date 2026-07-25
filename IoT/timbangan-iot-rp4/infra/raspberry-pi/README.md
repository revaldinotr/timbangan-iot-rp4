# Self-Host n8n di Raspberry Pi + Cloudflare Tunnel

Panduan menjalankan n8n di Raspberry Pi dan mengeksposnya ke internet secara aman
lewat Cloudflare Tunnel — tanpa membuka port di router.

## Prasyarat

- Raspberry Pi (Pi 4 atau CM4) dengan Raspberry Pi OS dan akses SSH
- Akun Cloudflare dengan domain yang sudah dikonfigurasi
- Docker dan Docker Compose terpasang

---

## Bagian 1 — Cloudflare Tunnel

### 1. Buat tunnel

1. Masuk ke dashboard Cloudflare → **Zero Trust**
2. **Networks → Tunnels → Add a tunnel → Cloudflared**
3. Beri nama, mis. `raspberry-pi-tunnel`, lalu simpan
4. Akan muncul perintah instalasi berisi token — **catat token-nya, jaga kerahasiaannya**

> Token tunnel memberi kendali atas rute jaringan Anda. Perlakukan seperti kata sandi:
> simpan di `.env`, jangan pernah di-commit.

### 2. Pasang cloudflared di Raspberry Pi

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings

curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt update
sudo apt install cloudflared
```

> Ganti `bookworm` sesuai versi OS Anda (`bullseye` untuk Pi OS lama).
> Cek dengan `lsb_release -cs`.

### 3. Sambungkan tunnel

```bash
sudo cloudflared service install <TOKEN_TUNNEL_ANDA>
```

Raspberry Pi akan muncul sebagai *connected* di dashboard Cloudflare.

### 4. Arahkan subdomain

1. Di setup tunnel, klik **Next**, tentukan subdomain (mis. `n8n.domainanda.com`)
2. **Service**: pilih `HTTP`, URL `localhost:5678`
3. Simpan

---

## Bagian 2 — Menjalankan n8n

### 1. Siapkan konfigurasi

```bash
cd infra/raspberry-pi
cp .env.example .env
```

Buat kunci enkripsi:

```bash
openssl rand -hex 32
```

Isi `.env`: `N8N_ENCRYPTION_KEY`, `N8N_HOST`, `WEBHOOK_URL`, `STOK_PIN`,
serta user dan password basic auth.

> ⚠️ **Cadangkan `N8N_ENCRYPTION_KEY` di luar Raspberry Pi.** Tanpa kunci ini,
> seluruh credential yang tersimpan tidak dapat dipulihkan bila kartu SD rusak.

### 2. Jalankan

```bash
docker compose up -d
docker compose logs -f
```

### 3. Perbaiki masalah izin volume (bila muncul)

Bila log menunjukkan error permission:

```bash
docker compose stop
docker run --rm -v n8n_data:/home/node/.n8n alpine chown -R 1000:1000 /home/node/.n8n
docker compose start
docker compose logs -f
```

Migrasi database akan berjalan dan startup selesai normal.

### 4. Akses

Buka `https://n8n.domainanda.com`, lalu selesaikan setup awal.

---

## Catatan Khusus Raspberry Pi

**Kartu SD.** n8n cukup sering menulis ke disk. Untuk pemakaian jangka panjang,
gunakan SSD via USB atau kartu SD kelas industri — kartu biasa akan cepat aus.

**Memori.** Pada CM4 2 GB yang juga menjalankan `main.py` (kamera + inferensi TFLite),
RAM bisa menjadi ketat. Pertimbangkan menjalankan n8n di perangkat terpisah bila
sistem terasa berat.

**Suhu.** Beban inferensi berkelanjutan membuat CM4 panas. Pastikan ada pendingin
pasif atau kipas, terutama bila alat dipasang di dalam casing tertutup.

---

## Sumber

Bagian tunnel dan Docker diadaptasi dari tutorial
[Self-Hosting n8n on a Raspberry Pi](https://youtu.be/GPRj9N4C2fs), disesuaikan
dengan kebutuhan proyek ini.
