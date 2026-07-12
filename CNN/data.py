"""Data loading, stratified splitting, transforms, and class weights.

The dataset is a single folder of class subdirectories (ImageFolder layout) with
no predefined train/val/test split, so we split it programmatically and
stratify by class to keep every class represented in each split -- important
because the classes are heavily imbalanced (e.g. Stab_wound has only 23 images).
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import List, Tuple

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from torchvision.datasets import ImageFolder

import config


class TransformedSubset(Dataset):
    """Wraps a Subset so a split-specific transform is applied.

    ``ImageFolder`` holds a single transform, but train and eval need different
    ones (augmentation vs. deterministic center-crop). This wrapper lets the
    same underlying images be served with the correct transform per split.
    """

    def __init__(self, subset: Subset, transform, label_map: List[int] | None = None):
        self.subset = subset
        self.transform = transform
        # label_map[original_target] -> effective target (for class merging).
        self.label_map = label_map
        # Reach through to the underlying ImageFolder for raw sample access.
        self.base: ImageFolder = subset.dataset  # type: ignore[assignment]

    def __len__(self) -> int:
        return len(self.subset)

    def __getitem__(self, idx: int):
        # subset.indices maps our idx to the position in the base ImageFolder.
        base_idx = self.subset.indices[idx]
        path, target = self.base.samples[base_idx]
        if self.label_map is not None:
            target = self.label_map[target]
        image = self.base.loader(path)  # PIL image
        image = image.convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, target


def build_transforms() -> Tuple[transforms.Compose, transforms.Compose]:
    """Return (train_transform, eval_transform)."""
    normalize = transforms.Normalize(config.IMAGENET_MEAN, config.IMAGENET_STD)

    train_tf = transforms.Compose(
        [
            transforms.RandomResizedCrop(config.IMG_SIZE, scale=(0.6, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(p=0.2),
            # TrivialAugmentWide: strong, parameter-free automatic augmentation
            # policy that reliably helps generalization on small datasets.
            transforms.TrivialAugmentWide(),
            transforms.ToTensor(),
            normalize,
            # RandomErasing (a.k.a. cutout) after normalization for extra regularization.
            transforms.RandomErasing(p=0.25),
        ]
    )

    eval_tf = transforms.Compose(
        [
            transforms.Resize(config.RESIZE_SIZE),
            transforms.CenterCrop(config.IMG_SIZE),
            transforms.ToTensor(),
            normalize,
        ]
    )
    return train_tf, eval_tf


def _stratified_split(labels: List[int]) -> Tuple[List[int], List[int], List[int]]:
    """Two-step stratified split into train/val/test index lists."""
    indices = np.arange(len(labels))
    labels_arr = np.array(labels)

    # First carve out the test set.
    train_val_idx, test_idx = train_test_split(
        indices,
        test_size=config.TEST_SPLIT,
        stratify=labels_arr,
        random_state=config.SEED,
    )

    # Then split the remainder into train and val. Adjust the val fraction so it
    # is measured against the whole dataset, not just the remainder.
    val_relative = config.VAL_SPLIT / (1.0 - config.TEST_SPLIT)
    train_idx, val_idx = train_test_split(
        train_val_idx,
        test_size=val_relative,
        stratify=labels_arr[train_val_idx],
        random_state=config.SEED,
    )
    return train_idx.tolist(), val_idx.tolist(), test_idx.tolist()


def _load_or_create_split(labels: List[int]) -> Tuple[List[int], List[int], List[int]]:
    """Reuse a persisted split if present (reproducibility), else create one."""
    if os.path.exists(config.SPLIT_PATH):
        with open(config.SPLIT_PATH, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        # Only reuse if it matches the current dataset size.
        if saved.get("dataset_size") == len(labels):
            return saved["train"], saved["val"], saved["test"]

    train_idx, val_idx, test_idx = _stratified_split(labels)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(config.SPLIT_PATH, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "dataset_size": len(labels),
                "train": train_idx,
                "val": val_idx,
                "test": test_idx,
            },
            fh,
        )
    return train_idx, val_idx, test_idx


def resolve_classes(original_classes: List[str], merged_map: dict):
    """Apply optional class merging as a label remap (no files are moved).

    Args:
        original_classes: the ImageFolder class names (alphabetical).
        merged_map: {new_name: [member_folder_class, ...]} from config.

    Returns:
        (effective_classes, label_map) where effective_classes is the sorted
        list of resulting class names and label_map[original_index] gives the
        effective (possibly merged) class index.
    """
    member_to_group = {}
    for new_name, members in (merged_map or {}).items():
        for m in members:
            if m not in original_classes:
                raise ValueError(
                    f"MERGED_CLASSES references '{m}', which is not a folder in "
                    f"the dataset. Available classes: {original_classes}"
                )
            member_to_group[m] = new_name

    effective_classes = sorted({member_to_group.get(c, c) for c in original_classes})
    new_index = {name: i for i, name in enumerate(effective_classes)}
    label_map = [new_index[member_to_group.get(c, c)] for c in original_classes]
    return effective_classes, label_map


def compute_class_weights(labels: List[int], num_classes: int) -> torch.Tensor:
    """Inverse-frequency weights: N / (num_classes * count_c)."""
    counts = Counter(labels)
    total = len(labels)
    weights = [
        total / (num_classes * counts.get(c, 1)) for c in range(num_classes)
    ]
    return torch.tensor(weights, dtype=torch.float32)


def build_datasets(data_dir: str):
    """Build train/val/test datasets plus metadata.

    Returns a dict with datasets, class_names, and train-set class weights.
    """
    train_tf, eval_tf = build_transforms()

    # Base dataset (no transform here; the wrapper applies per-split transforms).
    base = ImageFolder(data_dir)
    labels = [target for _, target in base.samples]

    # Resolve optional class merging into effective class names + a label remap.
    class_names, label_map = resolve_classes(base.classes, config.MERGED_CLASSES)
    num_classes = len(class_names)

    # Stratify on the ORIGINAL fine-grained labels so every sub-type (incl. the
    # tiny Stab_wound) stays represented across splits; the split itself is reused
    # from split.json when present.
    train_idx, val_idx, test_idx = _load_or_create_split(labels)

    train_ds = TransformedSubset(Subset(base, train_idx), train_tf, label_map)
    val_ds = TransformedSubset(Subset(base, val_idx), eval_tf, label_map)
    test_ds = TransformedSubset(Subset(base, test_idx), eval_tf, label_map)

    # Class weights computed from the TRAIN split only (avoids leaking val/test),
    # using the effective (merged) labels.
    train_labels = [label_map[labels[i]] for i in train_idx]
    class_weights = compute_class_weights(train_labels, num_classes)

    return {
        "train": train_ds,
        "val": val_ds,
        "test": test_ds,
        "class_names": class_names,
        "num_classes": num_classes,
        "class_weights": class_weights,
    }


def build_dataloaders(data_dir: str, batch_size: int):
    """Convenience wrapper returning loaders + metadata."""
    ds = build_datasets(data_dir)

    train_loader = DataLoader(
        ds["train"],
        batch_size=batch_size,
        shuffle=True,
        num_workers=config.NUM_WORKERS,
    )
    val_loader = DataLoader(
        ds["val"],
        batch_size=batch_size,
        shuffle=False,
        num_workers=config.NUM_WORKERS,
    )
    test_loader = DataLoader(
        ds["test"],
        batch_size=batch_size,
        shuffle=False,
        num_workers=config.NUM_WORKERS,
    )

    return {
        "train_loader": train_loader,
        "val_loader": val_loader,
        "test_loader": test_loader,
        "class_names": ds["class_names"],
        "num_classes": ds["num_classes"],
        "class_weights": ds["class_weights"],
    }
