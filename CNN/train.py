"""Full fine-tuning trainer for the injury classifier.

This is a from-strong-pretrained, train-for-accuracy recipe (not a quick head-only
pass). It runs in two phases:

  Phase 1 - warmup (backbone frozen): train only the new classifier head so its
            random weights settle before they can disturb the pretrained features.
  Phase 2 - fine-tune (whole network): unfreeze everything and train with a
            *discriminative* learning rate (lower LR on the pretrained backbone,
            higher on the head), a cosine schedule with linear warmup, strong
            augmentation, and an exponential moving average (EMA) of the weights.

The EMA copy is what gets evaluated and saved; EMA weights are consistently a bit
more accurate and more stable than the raw training weights. The best checkpoint is
chosen by validation macro-F1 (robust to the class imbalance).

Usage:
    python train.py                          # full run with config defaults
    python train.py --arch resnet50          # heavier backbone (slower, CPU)
    python train.py --epochs 80 --warmup-epochs 4
    python train.py --arch mobilenet_v3_large
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
from tqdm import tqdm

import config
from data import build_dataloaders
from model import AVAILABLE_ARCHS, build_model, set_backbone_trainable, split_params


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Full fine-tuning trainer")
    p.add_argument("--data-dir", default=config.DATA_DIR)
    p.add_argument("--arch", default=config.ARCH, choices=AVAILABLE_ARCHS)
    p.add_argument("--epochs", type=int, default=config.EPOCHS)
    p.add_argument("--warmup-epochs", type=int, default=config.WARMUP_EPOCHS,
                   help="Head-only epochs before unfreezing the backbone")
    p.add_argument("--batch-size", type=int, default=config.BATCH_SIZE)
    p.add_argument("--lr", type=float, default=config.LR, help="Head learning rate")
    p.add_argument("--dropout", type=float, default=config.DROPOUT)
    return p.parse_args()


def train_one_epoch(model, ema_model, loader, criterion, optimizer, device) -> float:
    model.train()
    total_loss = 0.0
    for images, targets in tqdm(loader, desc="train", leave=False):
        images = images.to(device)
        targets = targets.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        # Update the EMA weights after every optimizer step.
        ema_model.update_parameters(model)

        total_loss += loss.item() * images.size(0)
    return total_loss / max(len(loader.dataset), 1)


@torch.no_grad()
def evaluate_model(eval_module, loader, criterion, device):
    eval_module.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_targets: list[int] = []
    for images, targets in tqdm(loader, desc="val", leave=False):
        images = images.to(device)
        targets = targets.to(device)
        outputs = eval_module(images)
        total_loss += criterion(outputs, targets).item() * images.size(0)
        all_preds.extend(outputs.argmax(dim=1).cpu().tolist())
        all_targets.extend(targets.cpu().tolist())

    avg_loss = total_loss / max(len(loader.dataset), 1)
    acc = float(np.mean(np.array(all_preds) == np.array(all_targets)))
    macro_f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)
    return avg_loss, acc, macro_f1


def _retry_io(fn, what: str, retries: int = 6, delay: float = 1.0) -> bool:
    """Run a file-writing fn, retrying transient locks (common on Windows:
    antivirus scans, a file open in another program). Returns True on success.
    Never raises -- a logging/checkpoint hiccup must not kill a long training run.
    """
    for attempt in range(1, retries + 1):
        try:
            fn()
            return True
        except (PermissionError, OSError) as e:
            if attempt == retries:
                print(f"  [warn] could not write {what} after {retries} tries "
                      f"({e}); continuing.")
                return False
            time.sleep(delay * attempt)
    return False


def append_log_row(row: list) -> None:
    """Append one row to the training-log CSV (non-fatal, retried)."""
    def _write():
        with open(config.TRAINING_LOG_PATH, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(row)
    _retry_io(_write, "training_log.csv")


def save_checkpoint(module, is_ema, args, class_names, num_classes, val_f1) -> bool:
    payload = {
        "state_dict": module.state_dict(),
        "class_names": class_names,
        "num_classes": num_classes,
        "arch": args.arch,
        "dropout": args.dropout,
        "img_size": config.IMG_SIZE,
        "val_f1": val_f1,
        "ema": is_ema,
    }
    # Write to a temp file first, then atomically replace, so a lock can never
    # leave a half-written checkpoint.
    tmp = config.BEST_MODEL_PATH + ".tmp"
    ok = _retry_io(lambda: torch.save(payload, tmp), "checkpoint (tmp)")
    if ok:
        ok = _retry_io(lambda: os.replace(tmp, config.BEST_MODEL_PATH), "checkpoint")
    return ok


def validate_and_select(model, ema_model, loader, criterion, device):
    """Evaluate both the raw and EMA weights; return the better of the two.

    EMA weights win late in training but lag early (they take many steps to catch
    up), so picking the better of the two each epoch is robust across run lengths.

    Returns: (val_loss, val_acc, val_f1, best_module, is_ema).
    """
    raw_loss, raw_acc, raw_f1 = evaluate_model(model, loader, criterion, device)
    ema_loss, ema_acc, ema_f1 = evaluate_model(ema_model.module, loader, criterion, device)
    if ema_f1 >= raw_f1:
        return ema_loss, ema_acc, ema_f1, ema_model.module, True
    return raw_loss, raw_acc, raw_f1, model, False


def main() -> None:
    args = parse_args()
    set_seed(config.SEED)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    device = config.DEVICE

    print(f"Device: {device} | Arch: {args.arch}")
    print(f"Epochs: {args.epochs} (warmup {args.warmup_epochs}) | "
          f"batch {args.batch_size} | head LR {args.lr}")

    data = build_dataloaders(args.data_dir, args.batch_size)
    class_names = data["class_names"]
    num_classes = data["num_classes"]
    print(f"Classes ({num_classes}): {class_names}")
    print(f"Train batches: {len(data['train_loader'])}, "
          f"Val batches: {len(data['val_loader'])}")

    with open(config.CLASS_NAMES_PATH, "w", encoding="utf-8") as fh:
        json.dump(class_names, fh, indent=2)

    model = build_model(args.arch, num_classes, dropout=args.dropout).to(device)

    # EMA tracks *all* parameters and buffers (use_buffers=True keeps BatchNorm
    # running stats consistent with the averaged weights, so we can evaluate the
    # EMA model directly without recomputing BN statistics).
    ema_model = AveragedModel(
        model,
        multi_avg_fn=get_ema_multi_avg_fn(config.EMA_DECAY),
        use_buffers=True,
    )

    class_weights = data["class_weights"].to(device)
    criterion = nn.CrossEntropyLoss(
        weight=class_weights, label_smoothing=config.LABEL_SMOOTHING
    )

    def _write_header():
        with open(config.TRAINING_LOG_PATH, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(
                ["epoch", "phase", "train_loss", "val_loss", "val_acc", "val_f1", "lr"]
            )
    _retry_io(_write_header, "training_log.csv header")

    best_val_f1 = -1.0
    epochs_without_improvement = 0
    warmup_epochs = min(args.warmup_epochs, args.epochs)

    # ---------------- Phase 1: warmup (backbone frozen, head only) ----------
    set_backbone_trainable(model, False)
    _, head_params = split_params(model)
    optimizer = torch.optim.AdamW(
        head_params, lr=args.lr, weight_decay=config.WEIGHT_DECAY
    )

    for epoch in range(1, warmup_epochs + 1):
        print(f"\n[warmup] Epoch {epoch}/{warmup_epochs}")
        train_loss = train_one_epoch(
            model, ema_model, data["train_loader"], criterion, optimizer, device
        )
        val_loss, val_acc, val_f1, best_module, is_ema = validate_and_select(
            model, ema_model, data["val_loader"], criterion, device
        )
        lr_now = optimizer.param_groups[0]["lr"]
        tag = "ema" if is_ema else "raw"
        print(f"  train_loss={train_loss:.4f} | "
              f"val[{tag}]: loss={val_loss:.4f} acc={val_acc:.3f} f1={val_f1:.3f}")
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            if save_checkpoint(best_module, is_ema, args, class_names, num_classes, best_val_f1):
                print(f"  -> saved new best ({tag}, val_f1={best_val_f1:.3f})")
        append_log_row([epoch, "warmup", f"{train_loss:.4f}", f"{val_loss:.4f}",
                        f"{val_acc:.4f}", f"{val_f1:.4f}", lr_now])

    # ---------------- Phase 2: fine-tune (whole network) --------------------
    fine_tune_epochs = args.epochs - warmup_epochs
    if fine_tune_epochs > 0:
        set_backbone_trainable(model, True)
        backbone_params, head_params = split_params(model)
        optimizer = torch.optim.AdamW(
            [
                {"params": backbone_params, "lr": args.lr * config.BACKBONE_LR_MULT},
                {"params": head_params, "lr": args.lr},
            ],
            weight_decay=config.WEIGHT_DECAY,
        )

        # Linear LR warmup for the first couple of fine-tune epochs, then cosine
        # decay to ~0 over the rest.
        lr_warmup = min(config.LR_WARMUP_EPOCHS, max(fine_tune_epochs - 1, 1))
        warmup_sched = torch.optim.lr_scheduler.LinearLR(
            optimizer, start_factor=0.1, total_iters=lr_warmup
        )
        cosine_sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(fine_tune_epochs - lr_warmup, 1)
        )
        scheduler = torch.optim.lr_scheduler.SequentialLR(
            optimizer, schedulers=[warmup_sched, cosine_sched], milestones=[lr_warmup]
        )

        for i in range(1, fine_tune_epochs + 1):
            epoch = warmup_epochs + i
            print(f"\n[fine-tune] Epoch {epoch}/{args.epochs}")
            train_loss = train_one_epoch(
                model, ema_model, data["train_loader"], criterion, optimizer, device
            )
            val_loss, val_acc, val_f1, best_module, is_ema = validate_and_select(
                model, ema_model, data["val_loader"], criterion, device
            )
            lr_now = optimizer.param_groups[-1]["lr"]
            scheduler.step()

            tag = "ema" if is_ema else "raw"
            print(f"  train_loss={train_loss:.4f} | "
                  f"val[{tag}]: loss={val_loss:.4f} acc={val_acc:.3f} f1={val_f1:.3f} | "
                  f"lr={lr_now:.2e}")
            append_log_row([epoch, "finetune", f"{train_loss:.4f}", f"{val_loss:.4f}",
                            f"{val_acc:.4f}", f"{val_f1:.4f}", f"{lr_now:.6f}"])
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                epochs_without_improvement = 0
                if save_checkpoint(best_module, is_ema, args, class_names, num_classes, best_val_f1):
                    print(f"  -> saved new best ({tag}, val_f1={best_val_f1:.3f})")
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= config.EARLY_STOPPING_PATIENCE:
                    print(f"  Early stopping: no val_f1 improvement for "
                          f"{config.EARLY_STOPPING_PATIENCE} epochs.")
                    break

    print(f"\nBest val macro-F1: {best_val_f1:.3f}")
    print(f"Best model saved to: {config.BEST_MODEL_PATH}")
    print("Next: run  python evaluate.py  to measure test-set performance.")


if __name__ == "__main__":
    main()
