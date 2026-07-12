"""Live training status bar.

Run this in a separate terminal while train.py is training to see a single-line,
live-updating progress bar with the current epoch, best/last validation macro-F1,
and an ETA. It reads outputs/train_run.log (the training stdout), so it works even
when training runs in the background.

Usage:
    python monitor.py
    python monitor.py --log outputs/train_run.log --interval 2
"""
from __future__ import annotations

import argparse
import os
import re
import time

import config

# Regexes over the training stdout.
RE_TOTAL = re.compile(r"Epochs:\s*(\d+)")
RE_EPOCH = re.compile(r"\[(warmup|fine-tune)\]\s*Epoch\s*(\d+)/(\d+)")
RE_VAL = re.compile(r"val\[(\w+)\]:\s*loss=([\d.]+)\s*acc=([\d.]+)\s*f1=([\d.]+)")
RE_BEST = re.compile(r"saved new best\s*\([^,]+,\s*val_f1=([\d.]+)\)")
RE_DONE = re.compile(r"Best val macro-F1")


def parse_log(path: str) -> dict:
    """Extract current training state from the stdout log."""
    state = {
        "total": config.EPOCHS,
        "epoch": 0,
        "phase": "-",
        "last_f1": None,
        "last_acc": None,
        "best_f1": None,
        "done": False,
        "found": False,
    }
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except FileNotFoundError:
        return state

    state["found"] = True
    if (m := RE_TOTAL.search(text)):
        state["total"] = int(m.group(1))

    epochs = RE_EPOCH.findall(text)
    if epochs:
        phase, cur, _tot = epochs[-1]
        state["phase"] = phase
        state["epoch"] = int(cur)

    vals = RE_VAL.findall(text)
    if vals:
        state["last_acc"] = float(vals[-1][2])
        state["last_f1"] = float(vals[-1][3])

    bests = RE_BEST.findall(text)
    if bests:
        state["best_f1"] = max(float(b) for b in bests)

    state["done"] = bool(RE_DONE.search(text))
    return state


def format_hms(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def render(state: dict, width: int, secs_per_epoch: float | None) -> str:
    total = max(state["total"], 1)
    epoch = min(state["epoch"], total)
    frac = epoch / total
    filled = int(frac * width)
    bar = "#" * filled + "-" * (width - filled)

    best = f"{state['best_f1']:.3f}" if state["best_f1"] is not None else "  -  "
    last = f"{state['last_f1']:.3f}" if state["last_f1"] is not None else "  -  "
    phase = state["phase"]

    if state["done"]:
        tail = "DONE"
    elif secs_per_epoch and epoch < total:
        eta = secs_per_epoch * (total - epoch)
        tail = f"ETA {format_hms(eta)}"
    else:
        tail = "..."

    return (f"[{bar}] {epoch:>2d}/{total} {frac*100:5.1f}% | {phase:<9s} | "
            f"best f1 {best} | last f1 {last} | {tail}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live training status bar")
    p.add_argument("--log", default=os.path.join(config.OUTPUT_DIR, "train_run.log"))
    p.add_argument("--interval", type=float, default=2.0, help="Refresh seconds")
    p.add_argument("--width", type=int, default=30, help="Bar width in characters")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Monitoring {args.log}  (Ctrl+C to stop)\n")

    last_epoch = 0
    last_epoch_time: float | None = None
    secs_per_epoch: float | None = None

    try:
        while True:
            state = parse_log(args.log)

            # Estimate seconds/epoch from observed epoch transitions.
            now = time.time()
            if state["epoch"] > last_epoch:
                if last_epoch_time is not None and state["epoch"] - last_epoch > 0:
                    delta = (now - last_epoch_time) / (state["epoch"] - last_epoch)
                    # Smooth to avoid jumpiness.
                    secs_per_epoch = delta if secs_per_epoch is None else \
                        0.5 * secs_per_epoch + 0.5 * delta
                last_epoch = state["epoch"]
                last_epoch_time = now

            if not state["found"]:
                line = "waiting for training to start (no log yet)..."
            else:
                line = render(state, args.width, secs_per_epoch)

            # \r keeps it on one line; pad to clear any leftover characters.
            print("\r" + line.ljust(100), end="", flush=True)

            if state["done"]:
                print("\n\nTraining finished. Best val macro-F1 "
                      f"{state['best_f1']:.3f}." if state["best_f1"] else "\n\nDone.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n(monitor stopped; training continues in the background)")


if __name__ == "__main__":
    main()
