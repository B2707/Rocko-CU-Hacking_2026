#!/usr/bin/env python3
"""Interactively plot receiver CSV data with pan and zoom controls."""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="captures/receiver.csv")
    parser.add_argument("--center", type=float, default=8.0,
                        help="bandpass center frequency in Hz (default: 8)")
    parser.add_argument("--bandwidth", type=float, default=2.0,
                        help="bandpass width in Hz (default: 2, giving 7–9 Hz)")
    parser.add_argument("--save", help="optional path at which to save the plot")
    args = parser.parse_args()

    data = np.genfromtxt(args.csv, delimiter=",", names=True)
    data = np.atleast_1d(data)
    valid = np.isfinite(data["t"]) & np.isfinite(data["x"]) & np.isfinite(data["y"])
    t, x, y = data["t"][valid], data["x"][valid], data["y"][valid]

    fs = 1.0 / np.median(np.diff(t))
    half_width = args.bandwidth / 2.0
    low, high = args.center - half_width, args.center + half_width
    if low <= 0 or high >= fs / 2:
        parser.error(f"bandpass [{low:g}, {high:g}] Hz is invalid for fs={fs:g} Hz")
    sos = signal.butter(4, [low, high], btype="bandpass", fs=fs, output="sos")
    x_filtered = signal.sosfiltfilt(sos, x - np.mean(x))
    y_filtered = signal.sosfiltfilt(sos, y - np.mean(y))

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(t, x, linewidth=0.8, color="tab:blue")
    axes[0].set_ylabel("ADC X")
    axes[1].plot(t, y, linewidth=0.8, color="tab:orange")
    axes[1].set_ylabel("ADC Y")
    axes[2].plot(t, x_filtered, linewidth=0.8, color="tab:blue", label="X filtered")
    axes[2].plot(t, y_filtered, linewidth=0.8, color="tab:orange", alpha=0.8,
                 label="Y filtered")
    axes[2].set_ylabel("Filtered ADC")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_title(f"{low:g}–{high:g} Hz bandpass (center {args.center:g} Hz)")
    axes[2].legend(loc="upper right")

    for axis in axes:
        axis.grid(True, alpha=0.25)

    fig.suptitle(f"Receiver capture — {len(t):,} samples at {fs:.1f} Hz")
    fig.tight_layout()
    if args.save:
        fig.savefig(args.save, dpi=160)
        print(f"Saved {args.save}")
    plt.show()


if __name__ == "__main__":
    main()
