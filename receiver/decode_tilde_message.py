#!/usr/bin/env python3
"""Offline decode of a captured ``t,x,y`` CSV to a Rocko beacon frame.

Thin command-line front end over :mod:`decoder`. The frame layout, timing, and
Manchester mapping are fixed by the frozen contract in :mod:`protocol` — there
are no ``--message-bits`` style knobs, because the air interface is not
negotiable. Only the receiver-side DSP parameters (carrier, bandpass width) are
exposed for tuning against a noisy capture.

    python receiver/decode_tilde_message.py captures/trial.csv
    python receiver/decode_tilde_message.py trial.csv --carrier 8 --bandwidth 2
"""

import argparse
import csv
from pathlib import Path

import numpy as np

import decoder
from protocol import BANDWIDTH_HZ, CARRIER_HZ


def load_capture(path):
    data = np.atleast_1d(np.genfromtxt(path, delimiter=",", names=True))
    if not data.dtype.names or not {"t", "x", "y"}.issubset(data.dtype.names):
        raise ValueError("CSV must contain columns t,x,y")
    good = np.isfinite(data["t"]) & np.isfinite(data["x"]) & np.isfinite(data["y"])
    return data["t"][good], data["x"][good], data["y"][good]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--carrier", type=float, default=CARRIER_HZ)
    parser.add_argument("--bandwidth", type=float, default=BANDWIDTH_HZ)
    parser.add_argument("-o", "--output", help="optional per-bit score CSV")
    args = parser.parse_args()

    t, x, y = load_capture(args.csv)
    result = decoder.decode_repeats(t, x, y, carrier=args.carrier, bandwidth=args.bandwidth)
    best = result.frames[0]

    print(f"Sample rate:    {best.sample_rate:.3f} Hz")
    print(f"Frames found:   {len(result.frames)} ({result.agreement})")
    print(f"Message start:  sample {best.start_index}, t={best.start_time:.3f} s")
    print(f"Preamble score: {best.preamble_score:.4f} (two-channel maximum is 2)")
    for index, frame in enumerate(result.frames):
        flags = "".join(map(str, frame.flag_bits))
        print(f"  frame {index + 1}: {''.join(map(str, [0,1,1,1,1,1,1,0]))} {flags}"
              f"  -> {frame.label} ({frame.code})  t={frame.start_time:.3f}s")
    print(f"Decoded event:  {result.label} ({result.code})")

    if args.output:
        rows = [
            {
                "flag_bit": index,
                "score_0": scores[0],
                "score_1": scores[1],
                "decoded_bit": best.flag_bits[index],
            }
            for index, scores in enumerate(best.bit_scores)
        ]
        output = Path(args.output)
        with output.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"Scores:         {output}")


if __name__ == "__main__":
    main()
