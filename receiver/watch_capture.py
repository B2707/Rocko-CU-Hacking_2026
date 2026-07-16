#!/usr/bin/env python3
"""Read-only live plot for a CSV that another process is actively capturing."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
from scipy import signal


def parse_row(line: str):
    fields = line.strip().split(",")
    if len(fields) != 3:
        return None
    try:
        return tuple(map(float, fields))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--seconds", type=float, default=90.0)
    parser.add_argument("--sample-rate", type=float, default=200.0)
    parser.add_argument("--carrier", type=float, default=8.0)
    parser.add_argument("--bandwidth", type=float, default=1.5)
    parser.add_argument("--status-file", type=Path, help="optional live decode status text")
    args = parser.parse_args()

    capacity = max(100, round(args.seconds * args.sample_rate))
    raw_t, raw_x, raw_y = (deque(maxlen=capacity) for _ in range(3))
    total = 0
    handle = args.csv.open("r", encoding="utf-8", errors="replace")

    def drain():
        nonlocal total
        added = 0
        while True:
            line = handle.readline()
            if not line:
                break
            row = parse_row(line)
            if row is None:
                continue
            tv, xv, yv = row
            raw_t.append(tv)
            raw_x.append(xv)
            raw_y.append(yv)
            total += 1
            added += 1
        return added

    drain()
    low = args.carrier - args.bandwidth / 2
    high = args.carrier + args.bandwidth / 2
    sos = signal.butter(
        4, [low, high], btype="bandpass", fs=args.sample_rate, output="sos"
    )

    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
    fig.canvas.manager.set_window_title("Rocko — read-only growing-capture viewer")
    (raw1,) = axes[0].plot([], [], lw=.8, label="sensor 1")
    (raw2,) = axes[0].plot([], [], lw=.8, alpha=.75, label="sensor 2")
    (band1,) = axes[1].plot([], [], lw=.8, label="sensor 1")
    (band2,) = axes[1].plot([], [], lw=.8, alpha=.75, label="sensor 2")
    (env,) = axes[2].plot([], [], lw=1.0, color="#059669", label="8 Hz envelope")
    axes[0].set_ylabel("Raw ADC")
    axes[1].set_ylabel("Bandpass")
    axes[2].set_ylabel("Amplitude")
    axes[2].set_xlabel("Recent capture time (s)")
    axes[1].set_title(f"Fourth-order {low:g}–{high:g} Hz bandpass")
    for axis in axes:
        axis.grid(alpha=.25)
        axis.legend(loc="upper right")
    title = fig.suptitle("Waiting for samples…")
    plt.tight_layout()

    def update(_frame):
        drain()
        if len(raw_x) < 32:
            return raw1, raw2, band1, band2, env, title
        x = np.asarray(raw_x)
        y = np.asarray(raw_y)
        # Use a continuous display axis even if the Pico timestamp resets.
        display_t = np.arange(len(x), dtype=float) / args.sample_rate
        display_t -= display_t[-1]
        fx = signal.sosfiltfilt(sos, x - np.median(x))
        fy = signal.sosfiltfilt(sos, y - np.median(y))
        amplitude = np.sqrt(fx * fx + fy * fy)
        for artist, values in ((raw1, x), (raw2, y), (band1, fx), (band2, fy), (env, amplitude)):
            artist.set_data(display_t, values)
        for axis, values in ((axes[0], np.r_[x, y]), (axes[1], np.r_[fx, fy]), (axes[2], amplitude)):
            finite = values[np.isfinite(values)]
            if len(finite):
                lo, hi = np.percentile(finite, [.5, 99.5])
                padding = max((hi - lo) * .08, 1e-6)
                axis.set_ylim(lo - padding, hi + padding)
            axis.set_xlim(display_t[0], 0)
        status = ""
        if args.status_file and args.status_file.exists():
            try:
                status = "\n" + args.status_file.read_text().strip()
            except OSError:
                pass
        title.set_text(
            f"Read-only live viewer — {args.csv.name} — {total:,} samples{status}"
        )
        return raw1, raw2, band1, band2, env, title

    animation = FuncAnimation(fig, update, interval=500, blit=False, cache_frame_data=False)
    fig._rocko_animation = animation
    try:
        plt.show()
    finally:
        handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
