#!/usr/bin/env python3
"""Decode an 8 Hz OOK/Manchester message using a complex tilde preamble template.

Pipeline:
  1. Butterworth bandpass around the carrier.
  2. Hilbert transform to obtain a complex analytic signal.
  3. Normalized complex correlation with a Manchester '~' template.
  4. Decode subsequent bits by naive-max correlation against Manchester 0/1.
"""

import argparse
import csv
from pathlib import Path

import numpy as np
from scipy import signal


def load_capture(path):
    data = np.atleast_1d(np.genfromtxt(path, delimiter=",", names=True))
    if not data.dtype.names or not {"t", "x", "y"}.issubset(data.dtype.names):
        raise ValueError("CSV must contain columns t,x,y")
    good = np.isfinite(data["t"]) & np.isfinite(data["x"]) & np.isfinite(data["y"])
    return data["t"][good], data["x"][good], data["y"][good]


def manchester_levels(bits):
    # Regular OOK Manchester: 0 -> OFF,ON and 1 -> ON,OFF.
    return np.array([level for bit in bits
                     for level in ((0, 1) if bit == 0 else (1, 0))], dtype=float)


def complex_template(bits, half_samples, fs, carrier):
    gate = np.repeat(manchester_levels(bits), half_samples)
    time = np.arange(len(gate)) / fs
    return gate * np.exp(2j * np.pi * carrier * time)


def normalized_sliding_correlation(z, template):
    correlation = signal.fftconvolve(z, np.conj(template[::-1]), mode="valid")
    cumulative_energy = np.concatenate(([0.0], np.cumsum(np.abs(z) ** 2)))
    window_energy = cumulative_energy[len(template):] - cumulative_energy[:-len(template)]
    template_energy = np.vdot(template, template).real
    return np.abs(correlation) ** 2 / (template_energy * window_energy + 1e-15)


def template_score(channels, start, template):
    stop = start + len(template)
    template_energy = np.vdot(template, template).real
    score = 0.0
    for z in channels:
        segment = z[start:stop]
        segment_energy = np.vdot(segment, segment).real
        score += np.abs(np.vdot(template, segment)) ** 2 / (
            template_energy * segment_energy + 1e-15)
    return float(score)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--carrier", type=float, default=8.0)
    parser.add_argument("--bandwidth", type=float, default=2.0)
    parser.add_argument("--half-rate", type=float, default=0.5)
    parser.add_argument("--message-bits", type=int, default=16,
                        help="total message length including tilde (default: 16)")
    parser.add_argument("-o", "--output", help="optional per-bit score CSV")
    args = parser.parse_args()

    t, x, y = load_capture(args.csv)
    fs = 1.0 / np.median(np.diff(t))
    half_samples = round(fs / args.half_rate)
    low, high = args.carrier - args.bandwidth / 2, args.carrier + args.bandwidth / 2
    sos = signal.butter(4, [low, high], btype="bandpass", fs=fs, output="sos")

    channels = []
    for samples in (x, y):
        filtered = signal.sosfiltfilt(sos, samples - np.median(samples))
        channels.append(signal.hilbert(filtered))

    preamble_bits = np.array([0, 1, 1, 1, 1, 1, 1, 0], dtype=np.int8)
    preamble = complex_template(preamble_bits, half_samples, fs, args.carrier)

    # Add normalized correlation power from both ADC channels. The magnitude
    # removes unknown carrier phase while retaining coherent integration gain.
    correlation = sum(normalized_sliding_correlation(z, preamble) for z in channels)
    message_start = int(np.argmax(correlation))
    peak = float(correlation[message_start])

    zero_template = complex_template([0], half_samples, fs, args.carrier)
    one_template = complex_template([1], half_samples, fs, args.carrier)

    decoded = list(map(int, preamble_bits))
    rows = []
    bit_samples = 2 * half_samples
    for bit_index in range(8, args.message_bits):
        start = message_start + bit_index * bit_samples
        if start + bit_samples > len(t):
            raise ValueError(f"capture ends before bit {bit_index}")
        score_zero = template_score(channels, start, zero_template)
        score_one = template_score(channels, start, one_template)
        bit = int(score_one > score_zero)  # naive max
        decoded.append(bit)
        rows.append({
            "bit_index": bit_index,
            "time_s": float(t[start]),
            "score_0": score_zero,
            "score_1": score_one,
            "decoded_bit": bit,
        })

    binary = "".join(map(str, decoded))
    print(f"Bandpass:       {low:g}-{high:g} Hz")
    print(f"Sample rate:    {fs:.3f} Hz")
    print(f"Message start:  sample {message_start}, t={t[message_start]:.6f} s")
    print(f"Preamble score: {peak:.6f} (two-channel maximum is 2)")
    for row in rows:
        print(f"bit {row['bit_index']:2}: score0={row['score_0']:.6f} "
              f"score1={row['score_1']:.6f} -> {row['decoded_bit']}")
    print(f"Binary message: {binary}")

    if args.output:
        output = Path(args.output)
        with output.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"Scores:         {output}")


if __name__ == "__main__":
    main()
