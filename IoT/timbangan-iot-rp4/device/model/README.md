# Folder Model

Letakkan berkas model YOLOv5 TFLite Anda di sini:

```
device/model/best-fp32.tflite
```

Berkas model **tidak disertakan** dalam repositori karena ukurannya besar
(puluhan MB) dan tidak cocok disimpan di Git biasa.

## Spesifikasi Model

| Aspek | Nilai |
|---|---|
| Arsitektur | YOLOv5 |
| Format | TensorFlow Lite |
| Presisi | FP32 (bisa juga FP16) |
| Ukuran input | 640 × 640 piksel |
| Kelas | `kentang`, `tomat`, `wortel` |

Urutan kelas **harus** sama persis dengan `CLASS_NAMES` di `main.py`.
Bila Anda melatih ulang dengan kelas berbeda, perbarui juga daftar tersebut
beserta `CLASS_COLORS`.

## FP32 vs FP16

| | FP32 | FP16 |
|---|---|---|
| Akurasi objek kecil | Sedikit lebih baik | Sedikit menurun |
| Kecepatan inferensi | Lebih lambat | Lebih cepat |
| Kebutuhan RAM | Lebih besar | Lebih kecil |

Pada CM4 dengan RAM 2 GB, FP16 sering menjadi kompromi yang lebih nyaman.
Ubah `MODEL_PATH` di `main.py` bila Anda memakai berkas lain.

## Melatih Model Sendiri

1. Kumpulkan dan beri anotasi citra sayuran (Roboflow, LabelImg, dsb.)
2. Latih dengan [YOLOv5](https://github.com/ultralytics/yolov5)
3. Export ke TFLite:

   ```bash
   python export.py --weights runs/train/exp/weights/best.pt \
                    --include tflite --imgsz 640
   ```

4. Salin `best-fp32.tflite` ke folder ini

> Ukuran input ditentukan saat export. Bila Anda mengubahnya,
> `INPUT_SIZE` di `main.py` harus disesuaikan.
