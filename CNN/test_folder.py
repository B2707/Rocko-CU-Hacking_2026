"""Test the trained model on every image in a folder, using the filename as the
ground-truth label.

Each image's true class is inferred from its filename (e.g. "bruise.jpg",
"stab_wound.jpg", "abrasions (3).jpg"). Matching is tolerant of:
  * case, spaces, underscores, parentheses and trailing numbers, and
  * singular/plural differences (filename "bruise" -> class "Bruises").

For every image it prints the true label, the predicted label, and the model's
confidence, marks correct/incorrect, then reports overall accuracy plus a
per-class report over the images whose label could be identified. A per-image
CSV is written to outputs/test_folder_results.csv.

Usage:
    python test_folder.py                    # defaults to ./test_data
    python test_folder.py path/to/folder
    python test_folder.py --tta              # test-time augmentation (orig + h-flip)
"""
from __future__ import annotations

import argparse
import csv
import os
import re

import torch
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report

import config
# Reuse the exact same model loading and eval preprocessing as single-image predict.
from predict import build_eval_transform, load_model

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _normalize(text: str) -> str:
    """Lowercase and keep only letters (drops digits, spaces, underscores, parens)."""
    return re.sub(r"[^a-z]", "", text.lower())


def _aliases(name: str) -> set[str]:
    """Normalized alias strings for a name (plus a crude singular form)."""
    norm = _normalize(name)
    out = {norm}
    if norm.endswith("s"):
        out.add(norm[:-1])
    return out


def build_alias_map(class_names: list[str]) -> list[tuple[str, str]]:
    """Build (alias, target_class) pairs used to read a class from a filename.

    Includes each class name itself and, for any merged class in class_names,
    the names of its original members (from config.MERGED_CLASSES). So with
    Sharp_wound = Cut+Laceration+Stab_wound, a file "laceration.jpg" maps to
    "Sharp_wound".
    """
    pairs: list[tuple[str, str]] = []
    for cls in class_names:
        for alias in _aliases(cls):
            pairs.append((alias, cls))
    for merged_name, members in getattr(config, "MERGED_CLASSES", {}).items():
        if merged_name in class_names:
            for member in members:
                for alias in _aliases(member):
                    pairs.append((alias, merged_name))
    return pairs


def match_label(filename: str, alias_map: list[tuple[str, str]]) -> str | None:
    """Infer the ground-truth class from a filename.

    Returns the matching class name, or None if no class could be identified.
    When several aliases match, the longest (most specific) match wins.
    """
    fname_norm = _normalize(os.path.splitext(filename)[0])
    if not fname_norm:
        return None

    best: str | None = None
    best_len = -1
    for alias, target in alias_map:
        if alias and alias in fname_norm and len(alias) > best_len:
            best = target
            best_len = len(alias)
    return best


@torch.no_grad()
def predict_image(model, transform, path, device, tta):
    image = Image.open(path).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)
    probs = F.softmax(model(tensor), dim=1)
    if tta:
        flipped = torch.flip(tensor, dims=[3])  # horizontal flip
        probs = probs + F.softmax(model(flipped), dim=1)
    probs = probs.squeeze(0)
    idx = int(probs.argmax())
    return idx, float(probs[idx] / (2 if tta else 1))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test the model on a folder of images")
    p.add_argument("folder", nargs="?", default="test_data",
                   help="Folder of images (default: test_data)")
    p.add_argument("--tta", action="store_true",
                   help="Test-time augmentation (average original + horizontal flip)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    folder = args.folder
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"Not a folder: {folder}")

    device = config.DEVICE
    model, class_names = load_model(device)
    transform = build_eval_transform()
    alias_map = build_alias_map(class_names)

    files = sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    if not files:
        print(f"No images found in {folder}")
        return

    print(f"Device: {device}" + (" | TTA on" if args.tta else ""))
    print(f"Testing {len(files)} image(s) in '{folder}'\n")

    header = f"{'file':30s} {'true':16s} {'predicted':16s} {'conf':>6s}  result"
    print(header)
    print("-" * len(header))

    rows = []
    y_true: list[str] = []
    y_pred: list[str] = []
    unmatched: list[str] = []

    for fname in files:
        path = os.path.join(folder, fname)
        true_label = match_label(fname, alias_map)
        idx, conf = predict_image(model, transform, path, device, args.tta)
        pred_label = class_names[idx]

        if true_label is None:
            result = "  (no label in name)"
            unmatched.append(fname)
        else:
            correct = pred_label == true_label
            result = "OK " if correct else "XX "
            y_true.append(true_label)
            y_pred.append(pred_label)

        print(f"{fname[:30]:30s} {str(true_label or '?'):16s} "
              f"{pred_label:16s} {conf*100:5.1f}%  {result}")
        rows.append({
            "file": fname,
            "true_label": true_label or "",
            "predicted": pred_label,
            "confidence": f"{conf:.4f}",
            "correct": "" if true_label is None else str(pred_label == true_label),
        })

    # --- Summary ---------------------------------------------------------
    print()
    if y_true:
        acc = accuracy_score(y_true, y_pred)
        n_correct = sum(t == p for t, p in zip(y_true, y_pred))
        print(f"Accuracy on {len(y_true)} labeled image(s): "
              f"{acc:.3f} ({n_correct}/{len(y_true)})")

        # Per-class report over the labels that actually appear.
        present = sorted(set(y_true) | set(y_pred))
        print("\nPer-class report:")
        print(classification_report(
            y_true, y_pred, labels=present, zero_division=0
        ))
    else:
        print("No filenames could be matched to a class, so no accuracy was computed.")

    if unmatched:
        print(f"Unlabeled images (predicted only): {', '.join(unmatched)}")

    # --- CSV -------------------------------------------------------------
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(config.OUTPUT_DIR, "test_folder_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["file", "true_label", "predicted", "confidence", "correct"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nPer-image results saved to: {csv_path}")

    print(
        "\nDisclaimer: research/educational output only -- not a medical "
        "diagnosis. Do not use for clinical decisions."
    )


if __name__ == "__main__":
    main()
