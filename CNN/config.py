"""Central configuration for the injury image classifier.

All paths are resolved relative to this file so the scripts work regardless of
the current working directory.
"""
from __future__ import annotations

import os

import torch

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "Training_Data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

# Runtime artifacts (created by train.py)
BEST_MODEL_PATH = os.path.join(OUTPUT_DIR, "best_model.pt")
CLASS_NAMES_PATH = os.path.join(OUTPUT_DIR, "class_names.json")
SPLIT_PATH = os.path.join(OUTPUT_DIR, "split.json")
TRAINING_LOG_PATH = os.path.join(OUTPUT_DIR, "training_log.csv")
CONFUSION_MATRIX_PATH = os.path.join(OUTPUT_DIR, "confusion_matrix.png")

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42

# ---------------------------------------------------------------------------
# Data / split
# ---------------------------------------------------------------------------
IMG_SIZE = 224          # network input size
RESIZE_SIZE = 256       # resize target before center-crop at eval time
VAL_SPLIT = 0.15
TEST_SPLIT = 0.15       # train fraction is the remainder (~0.70)

# Optional class merging (applied as a label remap; your image folders are NOT
# modified on disk). Each entry maps a new combined class name to the on-disk
# folder classes that should be merged into it. Set to {} to disable merging.
#
# Cut, Laceration and Stab_wound are all sharp-force/open wounds that look alike,
# and Stab_wound alone has too few images (23) to learn well, so we combine them.
MERGED_CLASSES = {
    "Sharp_wound": ["Cut", "Laceration", "Stab_wound"],
}

# ---------------------------------------------------------------------------
# Training hyperparameters
# ---------------------------------------------------------------------------
# Default backbone. Override on the CLI with --arch.
# Options: efficientnet_b0, mobilenet_v3_large, mobilenet_v3_small, resnet50
ARCH = "efficientnet_b0"

BATCH_SIZE = 32
EPOCHS = 60                 # total epochs (warmup + fine-tune); early stopping ends it sooner
WARMUP_EPOCHS = 3           # phase 1: train the new head with the backbone frozen
LR = 1e-3                   # head learning rate
BACKBONE_LR_MULT = 0.1      # backbone LR = LR * this (discriminative fine-tuning)
LR_WARMUP_EPOCHS = 2        # linear LR warmup at the start of the fine-tune phase
WEIGHT_DECAY = 1e-4
LABEL_SMOOTHING = 0.1
DROPOUT = 0.3               # classifier-head dropout
EMA_DECAY = 0.998           # exponential moving average of weights (accuracy boost)
                            # ~500-step time constant; matures ~mid-training on this dataset
EARLY_STOPPING_PATIENCE = 12
# num_workers=0 is the safest choice on Windows + CPU (avoids spawn overhead).
NUM_WORKERS = 0

# ---------------------------------------------------------------------------
# ImageNet normalization (required for pretrained torchvision backbones)
# ---------------------------------------------------------------------------
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# ---------------------------------------------------------------------------
# Device (will be CPU on this machine, but auto-detect anyway)
# ---------------------------------------------------------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
