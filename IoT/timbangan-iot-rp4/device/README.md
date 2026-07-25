# Folder Model — YOLOv5 TFLite

Folder ini menampung model deteksi jenis sayuran yang dipakai `main.py`.

Berkas model **tidak disertakan** dalam repositori karena ukurannya beberapa MB dan
tidak cocok disimpan di Git biasa. Unduh dari
[**Releases**](../../../releases) atau latih sendiri mengikuti panduan di bawah.

---

## ⚠️ Penting: Nama Berkas

`main.py` mencari berkas bernama `best-fp32.tflite`:

```python
MODEL_PATH = os.path.join(_ROOT_DIR, "model", "best-fp32.tflite")
```

Namun **YOLOv5 tidak pernah menghasilkan berkas dengan nama itu.** Jalur export
TFLite pada YOLOv5 selalu memberi akhiran `-fp16`:

```python
# yolov5/export.py → export_tflite()
f = str(file).replace(".pt", "-fp16.tflite")
converter.target_spec.supported_types = [tf.float16]
```

Artinya berkas yang benar-benar Anda miliki bernama **`best-fp16.tflite`**.

Pilih salah satu:

**Opsi A — ganti nama berkas** (paling cepat)

```bash
mv best-fp16.tflite best-fp32.tflite
```

**Opsi B — sesuaikan `main.py`** (lebih jujur secara penamaan)

```python
MODEL_PATH = os.path.join(_ROOT_DIR, "model", "best-fp16.tflite")
```

Bila nama tidak cocok, program berhenti saat memuat model.

### Soal FP32 vs FP16

Komentar di `main.py` menyebut export tanpa `--half` menghasilkan FP32. Ini **tidak
berlaku untuk jalur TFLite**. Konverter TFLite pada YOLOv5 menetapkan
`supported_types = [tf.float16]` tanpa memandang flag `--half`, sehingga keluarannya
selalu bobot float16.

Flag `--half` hanya berlaku untuk export PyTorch/ONNX di GPU. Menambahkannya pada
export TFLite justru menghasilkan galat:

```
AssertionError: --half only compatible with GPU export, i.e. use --device 0
```

Untuk memperoleh TFLite FP32 sungguhan, Anda harus mengonversi sendiri dari
`best_saved_model/` — lihat [bagian di bawah](#membuat-tflite-fp32-sungguhan).

Dalam praktiknya FP16 justru **lebih menguntungkan di CM4**: ukuran separuh, inferensi
lebih cepat, kebutuhan RAM lebih kecil, dengan penurunan akurasi yang umumnya tidak
terasa untuk tiga kelas sayuran berukuran besar dalam bingkai.

---

## Spesifikasi Model

Diambil dari log pelatihan yang sebenarnya:

| Aspek | Nilai |
|---|---|
| Arsitektur | YOLOv5n (nano) |
| Bobot awal | `yolov5n.pt` (pretrained COCO) |
| Lapisan | 157 |
| Parameter | 1.763.224 |
| Kompleksitas | 4,1 GFLOPs |
| Ukuran input | 640 × 640 piksel |
| Bentuk keluaran | `(1, 25200, 8)` |
| Kelas | `kentang`, `tomat`, `wortel` |
| Format | TensorFlow Lite, bobot float16 |
| Ukuran berkas | ±3,5 MB (`.tflite`) / ±3,7 MB (`.pt`) |

**Membaca bentuk keluaran `(1, 25200, 8)`:**

- `25200` = jumlah anchor pada tiga skala deteksi
  `(80² + 40² + 20²) × 3 anchor = (6400 + 1600 + 400) × 3`
- `8` = `cx, cy, w, h, objectness, kelas₀, kelas₁, kelas₂`

Nilai `8` inilah yang mengonfirmasi model dilatih untuk **tepat tiga kelas**. Bila
Anda melatih ulang dengan jumlah kelas berbeda, angka ini ikut berubah dan
`postprocess()` di `main.py` akan menguraikannya secara otomatis — tetapi
`CLASS_NAMES` dan `CLASS_COLORS` **wajib** Anda sesuaikan manual.

> Urutan `CLASS_NAMES` harus sama persis dengan urutan pada `data.yaml` saat
> pelatihan. Urutan yang tertukar tidak menimbulkan error — model hanya akan
> menyebut tomat sebagai wortel.

---

## Dataset

| Aspek | Nilai |
|---|---|
| Sumber | Anotasi mandiri, diproses lewat Roboflow |
| Berkas | `DATA FINAL.zip` |
| Struktur | `train/images`, `train/labels`, `valid/`, `test/` |
| Citra latih | ±3.500 (219 iterasi × batch 16) |
| Augmentasi | 3 varian per citra sumber |
| Format label | YOLO (`class cx cy w h`, ternormalisasi) |

Jejak augmentasi Roboflow terlihat dari pola nama berkas — satu citra sumber muncul
tiga kali dengan hash berbeda:

```
tomato1_26-jpg_0_2623_jpg.rf.8b9e07263c4a424793b282222e9b4473.jpg
tomato1_26-jpg_0_2623_jpg.rf.8c78453a309a0e9713104e77eaa15749.jpg
tomato1_26-jpg_0_2623_jpg.rf.f5c2db35264f56aa6fb0f9b32d215b16.jpg
```

### `data.yaml`

```yaml
train: /content/DATA FINAL/train/images
val: /content/DATA FINAL/valid/images
test: /content/DATA FINAL/test/images

nc: 3
names: ['kentang', 'tomat', 'wortel']
```

> `nc` harus cocok dengan panjang `names`, dan urutan `names` menentukan indeks
> kelas pada berkas label.

---

## Melatih Ulang

Pelatihan dilakukan di **Google Colab** dengan GPU Tesla T4. Di CPU, 200 epoch akan
memakan waktu berhari-hari — gunakan GPU.

### 1. Siapkan lingkungan

```bash
!git clone https://github.com/ultralytics/yolov5
%cd yolov5
%pip install -qr requirements.txt
```

### 2. Unggah dan ekstrak dataset

```bash
!unzip -q "/content/DATA FINAL.zip" -d /content/
```

### 3. Buat `data.yaml`

Simpan berkas YAML di atas ke `/content/yolov5/data/data.yaml`.

### 4. Latih

```bash
!python train.py \
  --img 640 \
  --batch 16 \
  --epochs 200 \
  --data /content/yolov5/data/data.yaml \
  --weights yolov5n.pt \
  --cache
```

| Argumen | Alasan |
|---|---|
| `--img 640` | Harus sama dengan `INPUT_SIZE` di `main.py` |
| `--batch 16` | Muat di VRAM 15 GB milik T4 |
| `--epochs 200` | Cukup untuk dataset seukuran ini |
| `--weights yolov5n.pt` | Varian nano — paling ringan untuk CM4 |
| `--cache` | Cache citra di RAM, mempercepat pelatihan |

Hasil tersimpan di `runs/train/expN/`. **Catat nomor `expN`-nya** — nomor bertambah
tiap kali pelatihan diulang, dan salah menunjuk direktori adalah kesalahan paling
umum saat export.

### 5. Periksa hasil

```
runs/train/exp2/
├── weights/
│   ├── best.pt          ← mAP terbaik, ini yang dipakai
│   └── last.pt          ← epoch terakhir
├── results.png          ← kurva loss & mAP
├── confusion_matrix.png ← performa per kelas
└── PR_curve.png
```

Lihat `results.png`: bila loss validasi berbalik naik sementara loss latih terus
turun, model mengalami overfitting — kurangi epoch atau tambah data.

`confusion_matrix.png` memperlihatkan kelas mana yang tertukar. Kentang dan wortel
kadang tertukar pada pencahayaan rendah karena keduanya cenderung kecokelatan.

---

## Export ke TFLite

```bash
%cd /content/yolov5

!python export.py \
  --weights runs/train/exp2/weights/best.pt \
  --include tflite \
  --img 640 \
  --simplify

!ls -lh runs/train/exp2/weights/
```

Keluaran:

```
best-fp16.tflite      3.5M    ← ini yang dipakai perangkat
best_saved_model/             ← perantara TensorFlow
best.pt               3.7M
```

> **Jangan tambahkan `--half`.** Flag itu hanya berlaku untuk export GPU dan akan
> menggagalkan proses dengan `AssertionError`. Keluaran TFLite sudah float16 tanpa
> flag apa pun.

### Peringatan versi TensorFlow

```
WARNING ⚠️ using Tensorflow 2.20.0 > 2.13.1 might cause issue when exporting
the model to tflite
```

Peringatan ini muncul karena versi TensorFlow di Colab lebih baru daripada yang diuji
YOLOv5. Pada percobaan ini export tetap berhasil, tetapi bila Anda mengalami
kegagalan, turunkan versinya:

```bash
%pip install -q "tensorflow==2.13.1"
```

### Membuat TFLite FP32 sungguhan

Hanya bila Anda benar-benar membutuhkannya. Konversi manual dari SavedModel:

```python
import tensorflow as tf

converter = tf.lite.TFLiteConverter.from_saved_model(
    "runs/train/exp2/weights/best_saved_model"
)
# Tanpa target_spec.supported_types → bobot tetap float32
tflite_model = converter.convert()

with open("best-fp32.tflite", "wb") as f:
    f.write(tflite_model)
```

Berkas hasilnya ±2× lebih besar dan inferensinya lebih lambat di CM4. Ukur dulu
apakah selisih akurasinya sepadan sebelum memakainya.

---

## Memverifikasi Model

Jalankan di Raspberry Pi sebelum menjalankan `main.py`:

```python
#!/usr/bin/env python3
"""Verifikasi berkas model TFLite dapat dimuat dan bentuknya sesuai."""
import sys

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow as tf
    tflite = tf.lite

MODEL = "best-fp16.tflite"          # sesuaikan dengan nama berkas Anda
KELAS = ["kentang", "tomat", "wortel"]

itp = tflite.Interpreter(model_path=MODEL, num_threads=4)
itp.allocate_tensors()

inp = itp.get_input_details()[0]
out = itp.get_output_details()[0]

print(f"Input  : {inp['shape']}  {inp['dtype'].__name__}")
print(f"Output : {out['shape']}  {out['dtype'].__name__}")

h, w = inp["shape"][1], inp["shape"][2]
if (h, w) != (640, 640):
    print(f"❌ Ukuran input {h}×{w}, seharusnya 640×640")
    print("   Sesuaikan INPUT_SIZE di main.py, atau export ulang dengan --img 640")
    sys.exit(1)

n_out = out["shape"][2]
n_kelas = n_out - 5
if n_kelas != len(KELAS):
    print(f"❌ Model punya {n_kelas} kelas, CLASS_NAMES berisi {len(KELAS)}")
    sys.exit(1)

print(f"✅ Model valid — {n_kelas} kelas, input 640×640")
```

Keluaran yang benar:

```
Input  : [  1 640 640   3]  float32
Output : [    1 25200     8]  float32
✅ Model valid — 3 kelas, input 640×640
```

---

## Performa di Raspberry Pi CM4

Perkiraan pada CM4 2 GB, `NUM_THREADS=4`:

| Model | Ukuran | Inferensi | RAM |
|---|---|---|---|
| YOLOv5n FP16 | ±3,5 MB | ±300–600 ms | rendah |
| YOLOv5n FP32 | ±7 MB | ±500–900 ms | sedang |
| YOLOv5s FP16 | ±14 MB | ±1,5–3 dtk | tinggi |

Angka pasti bergantung suhu dan beban lain. Periksa throttling termal:

```bash
vcgencmd measure_temp
vcgencmd get_throttled     # 0x0 = normal
```

Inferensi lambat **tidak menghambat pembacaan berat** — keduanya berjalan di thread
terpisah. Yang terpengaruh hanyalah kecepatan konfirmasi jenis: dengan
`CONFIRM_FRAMES = 8` pada 500 ms per inferensi, jenis baru terkonfirmasi setelah
±4 detik.

Bila terasa terlalu lambat:

- Turunkan `CONFIRM_FRAMES` (mengorbankan kestabilan label)
- Turunkan `WEBCAM_WIDTH`/`WEBCAM_HEIGHT` ke 640×480
- Pastikan `NUM_THREADS=4`
- Pastikan memakai model FP16, bukan FP32

---

## Melatih dengan Kelas Berbeda

Untuk menambah jenis sayuran:

1. **Kumpulkan data** — minimal ±100 citra per kelas baru, dalam kondisi cahaya yang
   beragam dan menyerupai lokasi pemakaian sebenarnya
2. **Anotasi** — [Roboflow](https://roboflow.com), LabelImg, atau CVAT
3. **Augmentasi** — rotasi, kecerahan, blur; hindari flip vertikal karena sayuran
   jarang tampil terbalik
4. **Perbarui `data.yaml`** — sesuaikan `nc` dan `names`
5. **Latih ulang** dengan perintah yang sama
6. **Export** ke TFLite
7. **Perbarui `main.py`:**

```python
CLASS_NAMES  = ["kentang", "tomat", "wortel", "kubis"]
CLASS_COLORS = {
    "kentang": (0, 200, 0),
    "tomat"  : (0,  60, 255),
    "wortel" : (0, 165, 255),
    "kubis"  : (200, 200, 0),
}
```

> Urutan `CLASS_NAMES` **harus** sama dengan `names` di `data.yaml`. Ini kesalahan
> paling sering terjadi dan paling sulit disadari, karena tidak menimbulkan error —
> model hanya salah menyebut nama.

---

## Distribusi Model

Berkas `.tflite` dan `.pt` masuk `.gitignore`:

```gitignore
device/model/*.tflite
device/model/*.pt
device/model/*.onnx
```

Untuk membagikannya, gunakan **GitHub Releases**:

```bash
gh release create v1.0.0 \
  runs/train/exp2/weights/best-fp16.tflite \
  runs/train/exp2/weights/best.pt \
  --title "Model deteksi sayuran v1.0.0" \
  --notes "YOLOv5n, 3 kelas (kentang/tomat/wortel), 200 epoch, ±3.500 citra latih"
```

Sertakan dalam catatan rilis: jumlah kelas dan urutannya, ukuran input, jumlah epoch,
ukuran dataset, serta mAP dari `results.png`. Tanpa informasi ini, pengguna lain tidak
bisa tahu apakah model cocok untuk kebutuhan mereka.

---

## Masalah Umum

**Model gagal dimuat**
Periksa nama berkas — lihat [peringatan di awal](#-penting-nama-berkas).
`best-fp32.tflite` vs `best-fp16.tflite` adalah penyebab tersering.

**Deteksi tidak pernah muncul**
Pastikan berkas model ada, dan uji dengan skrip verifikasi di atas. `CONF_THRESH`
bawaan sudah sangat rendah (0,08); bila tetap nihil, masalahnya pada model atau
pencahayaan, bukan ambang batas.

**Nama kelas tertukar**
`CLASS_NAMES` tidak sesuai urutan `data.yaml`. Periksa berkas `data.yaml` yang dipakai
saat pelatihan.

**Export TFLite gagal**
Turunkan TensorFlow ke 2.13.1 seperti dijelaskan di atas.

**`AssertionError: --half only compatible with GPU export`**
Hapus flag `--half`. Export TFLite tidak memerlukannya.

**Direktori export salah**
`runs/train/exp` dan `runs/train/exp2` adalah dua pelatihan berbeda. Pastikan Anda
menunjuk direktori pelatihan yang benar.

---

## Rujukan

- [YOLOv5 — Ultralytics](https://github.com/ultralytics/yolov5)
- [Dokumentasi Ultralytics](https://docs.ultralytics.com)
- [Notebook Colab YOLOv5](https://colab.research.google.com/github/ultralytics/yolov5/blob/master/tutorial.ipynb)
- [Roboflow](https://roboflow.com) — anotasi dan augmentasi
- [Panduan konversi TFLite](https://www.tensorflow.org/lite/models/convert)

> YOLOv5 dirilis di bawah lisensi **AGPL-3.0**. Untuk penggunaan komersial, tinjau
> [Ultralytics Licensing](https://www.ultralytics.com/license). Lisensi MIT pada
> repositori ini berlaku untuk kode yang kami tulis, bukan untuk YOLOv5 maupun bobot
> hasil pelatihannya.
