#!/usr/bin/env python3
"""Injury-photo classifier for the QNX Raspberry Pi (project Rocko, E7).

Loads the team's converted EfficientNet-B0 `.tflite` via tflite-runtime (the
oss.qnx.com package that satisfies the competition's "AI module from oss.qnx.com"
requirement), classifies one photo, and prints the result as numbered events
(rocko.sh numbers each line). No camera: it reads a demo photo off disk.

The model is a generic drop-in (decision 3): its class labels come from a labels
file shipped next to it, never hardcoded. If the model is not installed yet the
script degrades gracefully with a clear message instead of a traceback.

Preprocessing matches the converted model's eval transform: aspect-preserving
resize (shorter edge -> 256, BILINEAR) + center-crop 224, fed as raw 0-255 RGB
float32 NHWC. The /255 + ImageNet-normalize + softmax are BAKED INTO the .tflite.

Deps on the Pi:  python3-tflite-runtime (oss.qnx.com), numpy, Pillow.
Usage:           python3 photo_classify.py [image] [--model M] [--labels L]
Via launcher:    rocko.sh photo [image]
"""

from __future__ import annotations

import argparse
import os
import sys

# Drop-in paths on the Pi (override on the CLI). injury.tflite (~16 MB) is NOT
# in the repo — see photo/README.md for the drop-in contract.
DEFAULT_MODEL = "/data/home/qnxuser/cnn/injury.tflite"
DEFAULT_LABELS = "/data/home/qnxuser/cnn/labels.txt"
DEFAULT_IMAGE = "/data/home/qnxuser/cnn/demo.jpg"

RESIZE_SIZE = 256  # shorter-edge target (torchvision Resize(256), BILINEAR)
IMG_SIZE = 224     # center-crop size (torchvision CenterCrop(224))
TOP_K = 3
DISCLAIMER = "Disclaimer: research/educational output only -- not a medical diagnosis."


def _emit(msg: str) -> None:
    """One event line; rocko.sh prefixes [#NNNN] + timestamp."""
    print(msg)
    sys.stdout.flush()


def load_labels(path: str) -> list[str]:
    """Class labels, one per line (blank lines ignored)."""
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def rank(probs, labels: list[str], k: int = TOP_K) -> list[tuple[str, float]]:
    """Top-k (label, probability) pairs, highest first. Pure Python."""
    order = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
    return [(labels[i], float(probs[i])) for i in order[:k]]


def preprocess(path: str):
    """PIL decode -> resize shorter edge to 256 (BILINEAR) -> center crop 224.

    Returns (1, 224, 224, 3) float32 in [0, 255], RGB. Heavy deps are imported
    lazily so this module still imports for unit tests without Pillow/numpy.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w <= h:
        new_w, new_h = RESIZE_SIZE, int(round(RESIZE_SIZE * h / w))
    else:
        new_h, new_w = RESIZE_SIZE, int(round(RESIZE_SIZE * w / h))
    img = img.resize((new_w, new_h), Image.BILINEAR)
    left = int(round((new_w - IMG_SIZE) / 2.0))
    top = int(round((new_h - IMG_SIZE) / 2.0))
    img = img.crop((left, top, left + IMG_SIZE, top + IMG_SIZE))
    return np.asarray(img, dtype=np.float32)[None, ...]


def _load_interpreter(model_path: str):
    """tflite-runtime on the Pi; ai_edge_litert is the drop-in on dev machines."""
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        from ai_edge_litert.interpreter import Interpreter
    interp = Interpreter(model_path=model_path)
    interp.allocate_tensors()
    return interp


def classify(image_path: str, model_path: str, labels: list[str]) -> list[tuple[str, float]]:
    """Run inference; return the top-k ranked (label, prob) list."""
    interp = _load_interpreter(model_path)
    in_idx = interp.get_input_details()[0]["index"]
    out_idx = interp.get_output_details()[0]["index"]
    interp.set_tensor(in_idx, preprocess(image_path))
    interp.invoke()
    probs = interp.get_tensor(out_idx)[0]
    return rank(probs, labels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify one injury photo with the Pi's tflite model (E7)."
    )
    parser.add_argument("image", nargs="?", default=DEFAULT_IMAGE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--labels", default=DEFAULT_LABELS)
    args = parser.parse_args(argv)

    # Graceful degrade (E7 / decision 3): clear message, never a traceback.
    if not os.path.exists(args.model):
        _emit(
            f"ERROR injury model not installed yet: {args.model} "
            "- drop injury.tflite there (see photo/README.md)"
        )
        return 3
    if not os.path.exists(args.labels):
        _emit(f"ERROR labels file missing: {args.labels}")
        return 3
    if not os.path.exists(args.image):
        _emit(f"ERROR photo not found: {args.image}")
        return 2

    try:
        labels = load_labels(args.labels)
        ranked = classify(args.image, args.model, labels)
    except ImportError as exc:
        _emit(
            f"ERROR photo inference deps missing: {exc} "
            "(need tflite-runtime + Pillow + numpy; apk add python3-tflite-runtime)"
        )
        return 4
    except Exception as exc:  # any decode/inference failure -> clean event
        _emit(f"ERROR photo inference failed: {exc}")
        return 5

    if not ranked:
        _emit("ERROR classifier returned no classes")
        return 5

    top_label, top_p = ranked[0]
    _emit(
        f"PHOTO CLASSIFIED: {top_label} ({top_p * 100:.1f}%) "
        f"[{os.path.basename(args.image)}]"
    )
    for position, (label, prob) in enumerate(ranked, 1):
        _emit(f"  {position}. {label:<16} {prob * 100:5.1f}%")
    _emit(DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
