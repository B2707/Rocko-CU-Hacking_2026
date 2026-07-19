#!/usr/bin/env python3
"""Offline static view of a recorded ``t,x,y`` capture, with the decoded event.

Same three-pane language as the live dashboard so a saved capture reviews the
same way:

    top     sensor 1 raw ADC
    middle  sensor 1 bandpass around the 8 Hz carrier
    bottom  combined carrier amplitude + decoded frame markers

    python receiver/plot_receiver.py captures/trial.csv
    python receiver/plot_receiver.py trial.csv --save review.png
"""

import argparse

import numpy as np
import matplotlib.pyplot as plt

import decoder
from protocol import BANDWIDTH_HZ, CARRIER_HZ

COLOR_RAW = "#2563eb"
COLOR_BAND = "#0891b2"
COLOR_AMP = "#059669"
COLOR_MARK = "#f59e0b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", default="captures/receiver.csv")
    parser.add_argument("--carrier", type=float, default=CARRIER_HZ)
    parser.add_argument("--bandwidth", type=float, default=BANDWIDTH_HZ)
    parser.add_argument("--save", help="optional path at which to save the figure")
    args = parser.parse_args()

    data = np.atleast_1d(np.genfromtxt(args.csv, delimiter=",", names=True))
    valid = np.isfinite(data["t"]) & np.isfinite(data["x"]) & np.isfinite(data["y"])
    t, x, y = data["t"][valid], data["x"][valid], data["y"][valid]
    fs = decoder.sample_rate_from_time(t)

    channels = decoder.analytic_channels(x, y, fs, args.carrier, args.bandwidth)
    band_x = np.real(channels[0])
    amplitude = np.abs(channels[0]) ** 2 + np.abs(channels[1]) ** 2
    amplitude = np.sqrt(amplitude)

    result = decoder.decode_repeats(t, x, y, carrier=args.carrier, bandwidth=args.bandwidth)

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(t, x, lw=0.8, color=COLOR_RAW)
    axes[0].set_ylabel("Sensor 1 raw ADC")
    axes[1].plot(t, band_x, lw=0.8, color=COLOR_BAND)
    axes[1].set_ylabel("Sensor 1 bandpass")
    axes[2].plot(t, amplitude, lw=1.1, color=COLOR_AMP)
    axes[2].set_ylabel("Carrier amplitude")
    axes[2].set_xlabel("Receiver time (s)")

    top = float(amplitude.max()) if amplitude.size else 1.0
    for index, frame in enumerate(result.frames):
        axes[2].axvline(frame.start_time, color=COLOR_MARK, lw=1.3, alpha=0.8)
        axes[2].scatter([frame.start_time], [top], marker="*", s=300,
                        color=COLOR_MARK, edgecolor="#7c2d12", zorder=6)
        axes[2].annotate(
            f"{frame.code}\n{frame.label}" if index == 0 else frame.code,
            xy=(frame.start_time, top), xytext=(4, -6), textcoords="offset points",
            fontsize=8, fontweight="bold", color="#7c2d12",
        )

    for axis in axes:
        axis.grid(True, alpha=0.22)
        axis.margins(x=0)

    fig.suptitle(
        f"Rocko capture — {len(t):,} samples @ {fs:.1f} Hz   "
        f"decoded: {result.label} ({result.code}), {result.agreement}",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    if args.save:
        fig.savefig(args.save, dpi=160)
        print(f"Saved {args.save}")
    plt.show()


if __name__ == "__main__":
    main()
