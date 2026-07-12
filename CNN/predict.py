"""Classify a single image with the trained model.

Usage:
    python predict.py path/to/image.jpg
    python predict.py path/to/image.jpg --topk 3

Prints the top-k predicted classes with softmax confidences.
"""
from __future__ import annotations

import argparse
import os

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

import config
from model import build_model


def build_eval_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(config.RESIZE_SIZE),
            transforms.CenterCrop(config.IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(config.IMAGENET_MEAN, config.IMAGENET_STD),
        ]
    )


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Classify one injury image")
    p.add_argument("image", help="Path to an image file")
    p.add_argument("--topk", type=int, default=3, help="How many predictions to show")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not os.path.exists(args.image):
        raise FileNotFoundError(f"Image not found: {args.image}")

    device = config.DEVICE
    model, class_names = load_model(device)
    transform = build_eval_transform()

    image = Image.open(args.image).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probs = F.softmax(logits, dim=1).squeeze(0)

    k = min(args.topk, len(class_names))
    top_probs, top_idx = probs.topk(k)

    print(f"\nImage: {args.image}")
    print(f"Top {k} predictions:")
    for rank, (p, idx) in enumerate(zip(top_probs.tolist(), top_idx.tolist()), 1):
        print(f"  {rank}. {class_names[idx]:20s} {p * 100:5.1f}%")

    print(
        "\nDisclaimer: research/educational output only -- not a medical "
        "diagnosis. Do not use for clinical decisions."
    )


if __name__ == "__main__":
    main()
