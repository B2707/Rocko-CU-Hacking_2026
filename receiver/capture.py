#!/usr/bin/env python3
"""
capture.py — capture receiver serial output to a CSV file.

The Pico 2W receiver prints one line per sample:

    t,x,y

This script opens the serial port, writes a header, and appends each
valid sample line to a CSV. It spawns `caffeinate` (macOS) so the Mac
does not idle-sleep during a long capture, then tears it down on exit.

Usage:
    python3 capture.py -p /dev/cu.usbmodemXXXX -b 115200 -o run1.csv
    python3 capture.py -p /dev/cu.usbmodemXXXX --duration 120

Requires pyserial:  pip3 install pyserial
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime

try:
    import serial
except ImportError:
    sys.exit("pyserial not found. Install with:  pip3 install pyserial")


def main():
    ap = argparse.ArgumentParser(description="Capture receiver serial data to CSV")
    ap.add_argument("-p", "--port", required=True,
                    help="serial port, e.g. /dev/cu.usbmodem1234567B1")
    ap.add_argument("-b", "--baud", type=int, default=115200,
                    help="baud rate (default 115200)")
    ap.add_argument("-o", "--out", help="output CSV path (default: capture_<ts>.csv)")
    ap.add_argument("-d", "--duration", type=float,
                    help="capture duration in seconds (default: run until Ctrl-C)")
    args = ap.parse_args()

    fname = args.out or f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Keep the Mac awake while capturing. `caffeinate -dimsu` with no command
    # runs until killed: prevents display sleep, idle sleep, disk idle, and
    # system sleep, and holds the assertion "user active".
    try:
        caf = subprocess.Popen(["caffeinate", "-dimsu"])
    except FileNotFoundError:
        print("warning: 'caffeinate' not found (not on macOS?). "
              "Continuing without sleep prevention.", file=sys.stderr)
        caf = None

    n = 0
    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser, \
             open(fname, "w", buffering=1) as f:
            f.write("t,x,y\n")
            print(f"Capturing {args.port} @ {args.baud} -> {fname} "
                  f"({'until Ctrl-C' if not args.duration else f'{args.duration}s'})")
            t0 = time.time()
            while True:
                if args.duration and (time.time() - t0) >= args.duration:
                    break
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="ignore").strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) != 3:
                    continue
                try:
                    float(parts[0])
                except ValueError:
                    continue  # skip non-data lines (e.g. debug prints)
                f.write(line + "\n")
                n += 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except serial.SerialException as e:
        sys.exit(f"Serial error: {e}")
    finally:
        if caf is not None:
            caf.terminate()
            try:
                caf.wait(timeout=2)
            except subprocess.TimeoutExpired:
                caf.kill()

    print(f"Done. {n} samples written to {fname}")


if __name__ == "__main__":
    main()
