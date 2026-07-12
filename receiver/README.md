# Receiver capture, visualization, and decoding

This directory contains the current receiver pipeline used with the Pico serial
sampler. It is intentionally split into small command-line programs so a new
GUI can reuse the CSV format and decoder while replacing Matplotlib. See
[`ALGORITHM.md`](ALGORITHM.md) for the complete protocol, DSP equations,
pseudocode, tone detector, and suggested GUI integration points.

## Data contract

The receiver appears as a USB serial device and emits one sample per line:

```text
t,x,y
123.450000,812,1571
```

- `t`: receiver time in seconds
- `x`, `y`: raw ADC values from the two sensor channels
- expected sample rate: 200 Hz

Captured files use the same header and rows. A replacement GUI can consume the
serial stream directly or tail the CSV without changing the signal-processing
scheme.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r receiver/requirements.txt
```

## Capture only

```bash
python receiver/capture.py \
  --port /dev/cu.usbmodem1201 \
  --out captures/trial.csv
```

## Interactive Matplotlib plot

```bash
python receiver/plot_receiver.py captures/trial.csv --center 8 --bandwidth 2
```

The three panels show raw X, raw Y, and both channels after the 7–9 Hz
bandpass. Use `--save output.png` to save the chart.

## Decode

```bash
python receiver/decode_tilde_message.py captures/trial.csv \
  --carrier 8 --bandwidth 2 --message-bits 16 \
  --output captures/trial_scores.csv
```

Decoder pipeline:

1. fourth-order Butterworth bandpass around 8 Hz;
2. Hilbert transform to produce complex analytic X/Y signals;
3. normalized complex correlation against the regular-Manchester tilde
   preamble (`01111110`);
4. correlation of each remaining bit against Manchester 0 (`OFF,ON`) and
   Manchester 1 (`ON,OFF`) templates;
5. naive maximum-score decision.

The command prints the binary message and writes per-bit template scores.

## Live view and automatic decode

```bash
python receiver/live_receiver.py --port /dev/cu.usbmodem1201
```

The reference Matplotlib UI displays:

- live raw X/Y;
- live 7–9 Hz bandpassed X/Y;
- carrier amplitude and adaptive tone threshold;
- tone/silence state and the decoded binary message.

After observing a tone, five continuous seconds without tone triggers the
same Hilbert/template decoder. Manchester OFF half-symbols are two seconds,
so they do not prematurely terminate a message.

The live frontend is replaceable. A richer GUI should preserve the serial/CSV
contract and either import or invoke `decode_tilde_message.py`, then visualize
its preamble and per-bit correlation scores.
