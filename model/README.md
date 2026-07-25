## Deskripsi

Proyek ini menggunakan varian ringan **YOLOv5n** (nano) sebagai model dasar (*pretrained weights*), kemudian dilakukan *fine-tuning* pada dataset sayuran kustom. Seluruh alur kerja — mulai dari *training*, validasi, hingga ekspor model — dijalankan pada notebook Google Colab.

Spesifikasi lingkungan pelatihan:

| Komponen | Versi / Nilai |
|----------|---------------|
| YOLOv5   | v7.0          |
| Python   | 3.12          |
| PyTorch  | 2.11.0 + CUDA 12.8 |
| GPU      | Tesla T4 (±15 GB) |
| Base model | `yolov5n.pt` |

---

## Kelas yang Dideteksi

Model dilatih untuk mengenali **3 kelas**:

| ID | Kelas   | Arti     |
|----|---------|----------|
| 0  | kentang | Potato   |
| 1  | tomat   | Tomato   |
| 2  | wortel  | Carrot   |

---

## Struktur Dataset

Dataset (`DATA FINAL.zip`) disusun dalam format YOLO dan dibagi menjadi *train* / *valid* / *test*. Setiap gambar memiliki file label `.txt` dengan format `class x_center y_center width height` (ternormalisasi).

```
DATA FINAL/
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
├── test/
│   ├── images/
│   └── labels/
└── data.yaml
```

Contoh isi `data.yaml`:

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 3
names: ['kentang', 'tomat', 'wortel']
```

---

## Persiapan & Instalasi

Clone repositori YOLOv5 dan pasang dependensinya:

```bash
git clone https://github.com/ultralytics/yolov5   # clone repo
cd yolov5
pip install -qr requirements.txt comet_ml          # install dependensi
```

Cek PyTorch & GPU dari dalam Python:

```python
import torch
import utils
display = utils.notebook_init()  # verifikasi environment
```

Ekstrak dataset:

```bash
unzip "/content/DATA FINAL.zip"
```

---

## Melatih Model (Training)

Latih model YOLOv5n pada dataset kustom:

```bash
python train.py \
  --img 640 \
  --batch 16 \
  --epochs 200 \
  --data /content/yolov5/data/data.yaml \
  --weights yolov5n.pt \
  --cache
```

**Parameter utama:**

| Flag | Nilai | Keterangan |
|------|-------|------------|
| `--img` | 640 | Ukuran input gambar |
| `--batch` | 16 | Ukuran batch |
| `--epochs` | 200 | Jumlah epoch pelatihan |
| `--weights` | `yolov5n.pt` | Bobot awal (transfer learning) |
| `--cache` | — | Cache gambar ke RAM agar training lebih cepat |

Waktu pelatihan: **±3,6 jam** untuk 200 epoch pada Tesla T4.

> 💡 Pelatihan dapat divisualisasikan secara *real-time* menggunakan **Comet**, **ClearML**, atau **TensorBoard**. Proyek ini menggunakan Comet.

---

## Hasil Pelatihan

Hasil validasi pada bobot terbaik (`best.pt`) setelah 200 epoch:

| Kelas    | Images | Instances | P (Precision) | R (Recall) | mAP@50 | mAP@50-95 |
|----------|:------:|:---------:|:-------------:|:----------:|:------:|:---------:|
| **all**  | 334    | 680       | 0.788         | 0.777      | 0.837  | 0.673     |
| kentang  | 334    | 326       | 0.800         | 0.763      | 0.862  | 0.742     |
| tomat    | 334    | 168       | 0.902         | 0.988      | 0.988  | 0.920     |
| wortel   | 334    | 186       | 0.662         | 0.579      | 0.659  | 0.356     |

**Ringkasan:**
- Performa terbaik pada kelas **tomat** (mAP@50 = 0.988).
- Kelas **wortel** paling menantang (mAP@50 = 0.659) — kemungkinan karena variasi bentuk/warna atau jumlah data yang lebih sedikit.

Grafik hasil (`results.png`) dan *confusion matrix* (`confusion_matrix.png`) tersimpan otomatis di `runs/train/exp2/`.

---

## Inferensi (Deteksi)

Jalankan deteksi menggunakan model hasil pelatihan:

```bash
python detect.py \
  --weights runs/train/exp2/weights/best.pt \
  --img 640 \
  --conf 0.25 \
  --source data/images
```

Sumber (`--source`) yang didukung antara lain:

```
--source 0                 # webcam
          img.jpg          # gambar
          vid.mp4          # video
          path/            # folder
          'path/*.jpg'     # glob
          'https://...'    # URL / stream
```

Hasil deteksi disimpan di `runs/detect/exp/`.

---

## Ekspor Model

Model dapat dikonversi ke berbagai format untuk *deployment*.

### ONNX

```bash
python export.py \
  --weights runs/train/exp2/weights/best.pt \
  --include onnx \
  --imgsz 640 \
  --device cpu \
  --simplify
```

### TFLite (FP32 — default)

```bash
python export.py \
  --weights runs/train/exp2/weights/best.pt \
  --include tflite \
  --img 640 \
  --simplify
```

> **Catatan:** Ekspor TFLite **FP16** (`--half`) hanya bisa dilakukan dengan GPU. Jika dijalankan di CPU akan muncul error:
> `AssertionError: --half only compatible with GPU export, i.e. use --device 0`.
> Gunakan `--device 0` bila ingin ekspor FP16.

---

## Struktur Output

Setelah pelatihan dan ekspor, file-file penting dikumpulkan ke dalam satu paket `.zip` untuk diunduh:

```
yolov5_training_package
├── best.pt                 # bobot PyTorch terbaik
├── best.onnx               # model format ONNX
├── best-fp16.tflite        # model format TFLite
├── data_custom.yaml        # konfigurasi dataset
├── coco128_custom.yaml
├── results.png             # grafik metrik pelatihan
└── confusion_matrix.png    # confusion matrix
```

Skrip pengumpulan file mencari pola seperti `**/best.pt`, `**/*.onnx`, `**/results.png`, dll., menyalinnya ke folder `yolov5_export/`, lalu memampatkannya menjadi arsip yang siap diunduh.

---

- [Ultralytics YOLOv5 – GitHub](https://github.com/ultralytics/yolov5)
- [Dokumentasi Ultralytics](https://docs.ultralytics.com/)
- [Comet – YOLOv5 Integration](https://docs.ultralytics.com/yolov5/tutorials/comet_logging_integration/)

---

