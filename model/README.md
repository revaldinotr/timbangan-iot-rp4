## Description

This project uses the lightweight **YOLOv5n** (nano) variant as its base model (*pretrained weights*), then performs *fine-tuning* on a custom vegetable dataset. The entire model development workflow — from *training* and performance validation to exporting the model into deployment formats — was carried out using the Google Colab environment.

Training environment specifications:

| Component | Version / Value |
|----------|---------------|
| YOLOv5   | v7.0          |
| Python   | 3.12          |
| PyTorch  | 2.11.0 + CUDA 12.8 |
| GPU      | Tesla T4 (±15 GB) |
| Base model | `yolov5n.pt` |

---

## Detected Classes

The model is trained to recognize **3 classes**:

| ID | Class   | Meaning  |
|----|---------|----------|
| 0  | kentang | Potato   |
| 1  | tomat   | Tomato   |
| 2  | wortel  | Carrot   |

---

## Dataset Structure

The dataset (`DATA FINAL.zip`) is organized in YOLO format and split into *train* / *valid* / *test*. Each image has a `.txt` label file in the format `class x_center y_center width height` (normalized).

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

Example `data.yaml` contents:

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 3
names: ['kentang', 'tomat', 'wortel']
```

---

## Setup & Installation

Clone the YOLOv5 repository and install its dependencies:

```bash
git clone https://github.com/ultralytics/yolov5   # clone repo
cd yolov5
pip install -qr requirements.txt comet_ml          # install dependencies
```

Check PyTorch & GPU from within Python:

```python
import torch
import utils
display = utils.notebook_init()  # verify environment
```

Extract the dataset:

```bash
unzip "/content/DATA FINAL.zip"
```

---

## Training the Model

Train the YOLOv5n model on the custom dataset:

```bash
python train.py \
  --img 640 \
  --batch 16 \
  --epochs 200 \
  --data /content/yolov5/data/data.yaml \
  --weights yolov5n.pt \
  --cache
```

**Key parameters:**

| Flag | Value | Description |
|------|-------|------------|
| `--img` | 640 | Input image size |
| `--batch` | 16 | Batch size |
| `--epochs` | 200 | Number of training epochs |
| `--weights` | `yolov5n.pt` | Initial weights (transfer learning) |
| `--cache` | — | Cache images to RAM for faster training |

Training time: **±3.6 hours** for 200 epochs on a Tesla T4.

> 💡 Training can be visualized in *real-time* using **Comet**, **ClearML**, or **TensorBoard**. This project uses Comet.

---

## Training Results

Validation results on the best weights (`best.pt`) after 200 epochs:

| Class    | Images | Instances | P (Precision) | R (Recall) | mAP@50 | mAP@50-95 |
|----------|:------:|:---------:|:-------------:|:----------:|:------:|:---------:|
| **all**  | 334    | 680       | 0.788         | 0.777      | 0.837  | 0.673     |
| kentang  | 334    | 326       | 0.800         | 0.763      | 0.862  | 0.742     |
| tomat    | 334    | 168       | 0.902         | 0.988      | 0.988  | 0.920     |
| wortel   | 334    | 186       | 0.662         | 0.579      | 0.659  | 0.356     |

**Summary:**
- Best performance on the **tomat** class (mAP@50 = 0.988).
- The **wortel** class is the most challenging (mAP@50 = 0.659) — likely due to variation in shape/color or a smaller amount of data.

Result plots (`results.png`) and the *confusion matrix* (`confusion_matrix.png`) are automatically saved in `runs/train/exp2/`.

---

## Inference (Detection)

Run detection using the trained model:

```bash
python detect.py \
  --weights runs/train/exp2/weights/best.pt \
  --img 640 \
  --conf 0.25 \
  --source data/images
```

Supported sources (`--source`) include:

```
--source 0                 # webcam
          img.jpg          # image
          vid.mp4          # video
          path/            # folder
          'path/*.jpg'     # glob
          'https://...'    # URL / stream
```

Detection results are saved in `runs/detect/exp/`.

---

## Model Export

The model can be converted into various formats for *deployment*.

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

> **Note:** TFLite **FP16** export (`--half`) can only be performed on a GPU. If run on CPU, the following error appears:
> `AssertionError: --half only compatible with GPU export, i.e. use --device 0`.
> Use `--device 0` if you want to export FP16.

---

## Output Structure

After training and export, the important files are collected into a single `.zip` package for download:

```
yolov5_training_package
├── best.pt                 # best PyTorch weights
├── best.onnx               # model in ONNX format
├── best-fp16.tflite        # model in TFLite format
├── data_custom.yaml        # dataset configuration
├── coco128_custom.yaml
├── results.png             # training metric plots
└── confusion_matrix.png    # confusion matrix
```

The file-collection script searches for patterns such as `**/best.pt`, `**/*.onnx`, `**/results.png`, etc., copies them into the `yolov5_export/` folder, then compresses them into an archive ready for download.

---

- [Ultralytics YOLOv5 – GitHub](https://github.com/ultralytics/yolov5)
- [Ultralytics Documentation](https://docs.ultralytics.com/)
- [Comet – YOLOv5 Integration](https://docs.ultralytics.com/yolov5/tutorials/comet_logging_integration/)

---
