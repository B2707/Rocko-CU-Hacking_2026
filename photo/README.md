# Photo injury classifier (E7)

A no-camera demo: classify an injury photo on the QNX Pi with the team's
converted CNN, via tflite-runtime (the oss.qnx.com package that satisfies the
competition's "AI module from oss.qnx.com" requirement). Runs standalone or as
`rocko.sh photo [image]`.

## What is in this folder

| File | Purpose |
|------|---------|
| `photo_classify.py` | inference script (generic drop-in: model path + labels file) |
| `labels.txt` | the 8 wound classes, one per line (order matches the model output) |

The 16 MB `injury.tflite` is **not** committed. It is produced by a separate
conversion of the team's EfficientNet-B0 (PyTorch, `CNN/outputs/best_model.pt`,
88.5% test acc) and dropped onto the Pi. PyTorch does not run on QNX; the
`.tflite` does, through tflite-runtime.

## Drop-in contract (Pi paths)

`photo_classify.py` defaults to a `cnn/` folder in the Pi home; override on the
CLI or via env in `rocko.sh`:

```
/data/home/qnxuser/cnn/injury.tflite     # the converted model (~16 MB, not in repo)
/data/home/qnxuser/cnn/labels.txt        # class labels (this file, deployed alongside)
/data/home/qnxuser/cnn/demo.jpg          # default demo photo
/data/home/qnxuser/cnn/photo_classify.py # this script
```

```
python3 photo_classify.py [image] --model <path> --labels <path>
rocko.sh photo [image]        # defaults to /data/home/qnxuser/cnn/demo.jpg
```

If the model (or labels) is not installed yet, the script prints a clear
`ERROR ... not installed yet` event and exits non-zero — it never crashes or
dumps a traceback (decision 3).

## Dependencies on the Pi

```
apk add python3-tflite-runtime    # oss.qnx.com — the competition AI module
# plus numpy and Pillow (PIL) available to python3
```

On a dev machine `ai_edge_litert` is used as the tflite-runtime drop-in.

## Preprocessing (must match the converted model's eval transform)

- PIL decode → RGB
- resize shorter edge to 256 (BILINEAR)
- center-crop 224
- feed raw 0-255 float32, NHWC `(1, 224, 224, 3)`

The `/255` + ImageNet-normalize + softmax are **baked into** `injury.tflite`, so
the script feeds the raw crop and reads a probability vector directly.

## Verified on the Pi (reference)

- `demo.jpg`  → `Sharp_wound` 92.9%
- `bruise.jpg` → `Bruises` 93.3%

## Output shape

```
PHOTO CLASSIFIED: Sharp_wound (92.9%) [demo.jpg]
  1. Sharp_wound       92.9%
  2. Abrasions          4.1%
  3. Surgical_wound     1.8%
Disclaimer: research/educational output only -- not a medical diagnosis.
```

Under `rocko.sh photo` each line is prefixed with `[#NNNN]` + a timestamp and
mirrored to `/tmp/rocko.log`.
