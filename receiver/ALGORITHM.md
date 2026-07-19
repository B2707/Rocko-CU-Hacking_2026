# Rocko receiver algorithm

The reference decode pipeline, implemented in `decoder.py` and driven by the
frozen contract in `protocol.py` (mirrors `docs/equipment-codes.md`). A GUI may
present the results differently but must not change these numbers — the Pi
transmitter depends on the identical contract.

## Frame contract (frozen)

| Parameter | Value |
|---|---:|
| ADC sample rate | 200 Hz |
| Carrier | 8 Hz |
| Receiver bandpass | 7–9 Hz |
| Bit duration | **1.0 s** (0.5 s Manchester half-symbols) |
| Preamble | `01111110` (`~`, 8 bits) |
| Payload | 4 flag bits (`bit3=fire bit2=trapped bit1=lost bit0=injured`) |
| Frame | 12 bits ≈ 12 s on air |
| Emergency repeats | 3× with 3 s gaps |
| Heartbeat | `0000` every 120 s (silence is the alarm) |
| End-of-message silence | 5 s (spans the 3 s repeat gaps, under the 120 s heartbeat) |

Regular OOK Manchester mapping:

```text
bit 1 -> tone,    no-tone     (ON,  OFF)
bit 0 -> no-tone, tone        (OFF, ON)
```

So the tilde preamble `01111110` has half-symbol gate `01 10 10 10 10 10 10 01`.

## 1. Acquisition

The Pico sends ASCII `t,x,y` lines over USB serial at 115200 baud (see
`pico_main.py`). `serial_source.py` validates each line and hands `(t, x, y)`
tuples to the capture/GUI; the two ADC channels are processed independently and
combined only at the correlation-score stage. `sample_source` is deliberately
separate from `decoder`, so the decode pipeline and its tests never touch a
serial port.

## 2. Bandpass + analytic signal

Each channel is median-centred and bandpass filtered with a 4th-order
Butterworth around the carrier, then Hilbert-transformed to a complex analytic
signal (`decoder.analytic_channels`):

```python
sos = butter(4, [7, 9], btype="bandpass", fs=200, output="sos")
z = hilbert(sosfiltfilt(sos, samples - median(samples)))
```

Offline decode uses zero-phase `sosfiltfilt`; the live display uses causal
`sosfilt` state because future samples are not available. The Hilbert transform
makes the decision insensitive to the unknown carrier phase.

## 3. Templates

For a Manchester half-symbol gate `g[n]` (`protocol.manchester_levels`), the
complex template is `s[n] = g[n] · exp(j2πf_c n/f_s)`, `f_c = 8 Hz`. OFF samples
contribute zero energy. The decoder builds the 8-bit preamble template and the
two single-bit templates `Manchester-0 = [OFF, ON]`, `Manchester-1 = [ON, OFF]`.
No captured waveform is used as a template, so it never overfits a trial.

## 4. Frame start (preamble search)

The preamble template slides across each analytic channel; normalized
correlation power is summed over both channels (`decoder.preamble_correlation`):

```text
        |Σ conj(s[n]) z[k+n]|²
C(k) = ------------------------------      Ctotal(k) = Cx(k) + Cy(k)   (max 2)
       (Σ|s|²)(Σ|z[k+n]|²) + eps
start = argmax Ctotal(k)
```

FFT convolution computes the numerator; a cumulative-energy trick computes the
denominator without re-summing each window.

## 5. Flag decode (naive-max)

Each of the 4 flag-bit windows after the preamble is correlated against the
Manchester-0 and Manchester-1 templates; the higher summed score wins
(`decoder.decode_flags_at`). The 4 bits map to a label + code via
`protocol.flags_to_event` (`0000` heartbeat, `1111` SOS, otherwise the OR of the
set flags, e.g. `0101` = trapped+injured).

## 6. Repeat awareness / majority vote

Emergencies repeat 3×. `decoder.decode_repeats` finds up to three preamble peaks
at least ~half a frame apart, decodes each, and takes the per-bit **majority**.
This survives one corrupted repeat out of three and reports agreement (e.g.
`3/3 frame(s) agreed`).

## 7. Live tone / end-of-message detector

`live_receiver.py` filters causally and tracks a 250 ms-smoothed carrier
amplitude `sqrt(fx² + fy²)`. Over a rolling 60 s window:

```text
floor = pct(amp, 10);  high = pct(amp, 90);  threshold = floor + 0.30(high - floor)
detector armed only when   high > max(3·floor, floor + min_separation)
```

A tone held for `tone_confirm` (0.3 s) arms the end detector; then `silence`
(5 s) of continuous no-tone flushes the capture and runs `decode_repeats`
in-process. 5 s comfortably spans the 3 s inter-repeat gaps (so all repeats are
captured) while staying well under the 120 s heartbeat.

## 8. Reference pseudocode

```text
open source (serial or CSV replay) and capture CSV
initialize causal 7-9 Hz filters
for each batch of (t, x, y):
    save samples; update raw / bandpass / amplitude panes
    if tone held >= tone_confirm:  arm end detector
    if armed and silence >= 5 s:
        result = decode_repeats(recent window)
        log numbered DECODE event; mark each frame start on the amplitude pane
```

## 9. Files

- `protocol.py` — frozen constants + flag↔event mapping.
- `decoder.py` — DSP, decode, repeat voting, synthetic generator.
- `serial_source.py` — serial + replay sources (only serial code).
- `eventlog.py` — numbered events (file + on-screen).
- `live_receiver.py` — live dashboard + detector + in-process decode.
- `rocko_receiver.py` — one-command launcher.
- `capture.py` / `plot_receiver.py` / `decode_tilde_message.py` — offline tools.
- `pico_main.py` — Pico firmware (t,x,y).
- `../tests/test_receiver.py` — synthetic-waveform decode tests, no hardware.
