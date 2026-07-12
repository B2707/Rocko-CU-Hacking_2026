"""Evaluate the trained model on the held-out test split.

Prints a per-class precision/recall/F1 report, overall accuracy and macro-F1,
and saves a confusion matrix image to outputs/confusion_matrix.png.

Usage:
    python evaluate.py
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")  # headless backend; writes PNG without a display
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from tqdm import tqdm

import config
from data import build_dataloaders
from model import build_model


def load_model(device):
    if not os.path.exists(config.BEST_MODEL_PATH):
        raise FileNotFoundError(
            f"No checkpoint at {config.BEST_MODEL_PATH}. Run train.py first."
        )
    ckpt = torch.load(config.BEST_MODEL_PATH, map_location=device)
    model = build_model(
        ckpt["arch"],
        ckpt["num_classes"],
        dropout=ckpt.get("dropout", 0.3),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt["class_names"]


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Evaluate on the test split")
    p.add_argument("--tta", action="store_true",
                   help="Test-time augmentation (average original + horizontal flip)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    device = config.DEVICE
    print(f"Device: {device}" + (" | TTA on" if args.tta else ""))

    model, class_names = load_model(device)

    # Reuses the persisted split.json, so the test set matches training.
    data = build_dataloaders(config.DATA_DIR, config.BATCH_SIZE)
    test_loader = data["test_loader"]

    all_preds: list[int] = []
    all_targets: list[int] = []
    with torch.no_grad():
        for images, targets in tqdm(test_loader, desc="test"):
            images = images.to(device)
            probs = torch.softmax(model(images), dim=1)
            if args.tta:
                flipped = torch.flip(images, dims=[3])  # horizontal flip
                probs = probs + torch.softmax(model(flipped), dim=1)
            preds = probs.argmax(dim=1)
            all_preds.extend(preds.cpu().tolist())
            all_targets.extend(targets.cpu().tolist())

    acc = accuracy_score(all_targets, all_preds)
    macro_f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)

    print("\n" + "=" * 60)
    print("Test set classification report")
    print("=" * 60)
    print(
        classification_report(
            all_targets,
            all_preds,
            labels=list(range(len(class_names))),
            target_names=class_names,
            zero_division=0,
        )
    )
    print(f"Overall accuracy: {acc:.3f}")
    print(f"Macro-F1:         {macro_f1:.3f}")

    # Flag any class with too few test images to trust its per-class metrics.
    from collections import Counter
    support = Counter(all_targets)
    scarce = [class_names[c] for c in range(len(class_names)) if support.get(c, 0) < 10]
    if scarce:
        print(
            f"\nNote: {', '.join(scarce)} has/have few test images (<10), so its "
            "per-class metrics are high-variance and not fully reliable."
        )

    # Confusion matrix image.
    cm = confusion_matrix(all_targets, all_preds, labels=list(range(len(class_names))))
    disp = ConfusionMatrixDisplay(cm, display_labels=class_names)
    fig, ax = plt.subplots(figsize=(10, 9))
    disp.plot(ax=ax, xticks_rotation=45, colorbar=False, values_format="d")
    ax.set_title("Injury classification - test confusion matrix")
    plt.tight_layout()
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    fig.savefig(config.CONFUSION_MATRIX_PATH, dpi=150)
    print(f"\nConfusion matrix saved to: {config.CONFUSION_MATRIX_PATH}")


if __name__ == "__main__":
    main()
