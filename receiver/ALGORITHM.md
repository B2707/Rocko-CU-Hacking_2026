# Receiver algorithm specification

This document describes the complete reference pipeline implemented in this
directory. A replacement GUI should preserve these numerical operations while
presenting the results differently.

## Protocol parameters

| Parameter | Value |
|---|---:|
| ADC sample rate | 200 Hz |
| Carrier | 8 Hz |
| Receiver bandpass | 7–9 Hz |
| Manchester half-symbol rate | 0.5/s |
| Half-symbol duration | 2 seconds / 400 samples |
| Bit duration | 4 seconds / 800 samples |
| Preamble | `01111110` (`~`, `0x7e`) |
| Current message length | 16 bits |
| End-of-message silence | 5 seconds |

Regular OOK Manchester mapping:

```text
bit 0 -> carrier OFF, carrier ON
bit 1 -> carrier ON,  carrier OFF
```

The tilde therefore has this half-symbol gate pattern:

```text
bits:     0  1  1  1  1  1  1  0
symbols: 01 10 10 10 10 10 10 01
```

## 1. Acquisition

The Pico sends ASCII lines over USB serial at 115200 baud:

```text
t,x,y
123.450000,812,1571
```

`capture.py` validates each line and writes it unchanged to a line-buffered
CSV. The two ADC channels are processed independently and combined only at the
correlation-score stage.

## 2. Bandpass filter

For offline decoding, each channel is centered by subtracting its median and
filtered with a fourth-order Butterworth bandpass:

```python
sos = scipy.signal.butter(
    4, [7, 9], btype="bandpass", fs=200, output="sos"
)
y = scipy.signal.sosfiltfilt(sos, samples - median)
```

`filtfilt` is zero-phase and is appropriate after capture. The live display
uses causal `sosfilt` state because future samples are not available.

## 3. Complex analytic signal

The real filtered waveform is converted to its analytic representation with a
Hilbert transform:

```text
z[n] = y[n] + j Hilbert(y[n])
```

This preserves carrier phase. Correlation magnitude is used later, making the
decision insensitive to an unknown constant phase between transmitter and
receiver.

## 4. Template generation

For a Manchester half-symbol gate sequence `g[n]`, the complex template is:

```text
s[n] = g[n] exp(j 2π fc n/fs)
```

where `fc = 8 Hz` and `fs = 200 Hz`. OFF samples have `g[n] = 0`; ON samples
have `g[n] = 1`.

The decoder generates three templates:

1. complete 8-bit tilde preamble;
2. Manchester zero: `[OFF, ON]`;
3. Manchester one: `[ON, OFF]`.

No captured waveform is used as a template, so the decoder does not overfit a
particular trial.

## 5. Preamble search

The tilde template slides across each analytic ADC channel. At candidate start
`k`, normalized correlation power is:

```text
                    |Σ conj(s[n]) z[k+n]|²
C(k) = ---------------------------------------------------
       (Σ |s[n]|²) (Σ |z[k+n]|²) + epsilon
```

The two sensor scores are added:

```text
Ctotal(k) = Cx(k) + Cy(k)
```

Each channel contributes at most 1, so the two-channel theoretical maximum is
2. The message start is the index with maximum combined correlation:

```text
start = argmax Ctotal(k)
```

FFT convolution computes the sliding numerator efficiently. Cumulative energy
computes the denominator without repeatedly summing each window.

## 6. Naive-max bit decoding

After the known eight-bit preamble, every four-second bit window is correlated
against both bit templates. Each score again adds normalized correlation power
from X and Y:

```text
score0 = score(window, Manchester-0 template)
score1 = score(window, Manchester-1 template)

bit = 1 if score1 > score0 else 0
```

The difference between the two scores is useful confidence information for a
GUI. `decode_tilde_message.py --output scores.csv` writes both scores, the bit
index, decision time, and decoded bit.

## 7. Live tone and end-of-message detector

`live_receiver.py` applies the same 7–9 Hz filter causally and calculates:

```text
amplitude[n] = sqrt(filtered_x[n]² + filtered_y[n]²)
```

A 250 ms exponential smoother stabilizes the amplitude. Over a rolling
60-second history:

```text
floor     = percentile(amplitude, 10)
high      = percentile(amplitude, 90)
threshold = floor + 0.30 (high - floor)
```

The detector is enabled only when the distribution has sufficient separation:

```text
high > max(3 * floor, floor + minimum_separation)
```

A tone must remain detected for 0.5 seconds to arm the end detector. Once
armed, five seconds without tone flushes the CSV and runs the offline complex
template decoder. Five seconds exceeds the protocol's two-second Manchester
OFF half-symbol, preventing normal OFF symbols from ending a message.

## 8. Reference pseudocode

```text
open serial port and CSV
initialize causal 7–9 Hz filters

for each serial batch:
    validate and save t,x,y
    filter X and Y
    update live raw/bandpass plots
    update smoothed carrier amplitude

    if tone persists >= 0.5 s:
        arm end detector

    if armed and silence persists >= 5 s:
        flush CSV
        offline_filter = zero_phase_bandpass(full capture)
        analytic = hilbert(offline_filter)
        start = peak(normalized_correlation(analytic, tilde_template))
        for each post-preamble bit:
            score0 = correlation(bit_window, zero_template)
            score1 = correlation(bit_window, one_template)
            append 1 if score1 > score0 else 0
        publish binary message, preamble score, and per-bit scores
```

## 9. GUI integration points

A richer GUI can initially execute the reference tools as subprocesses:

```bash
python receiver/decode_tilde_message.py capture.csv --output scores.csv
```

Useful visual elements include:

- raw and bandpassed X/Y traces;
- carrier envelope and adaptive threshold;
- tone/silence state;
- tilde correlation versus time and selected peak;
- preamble score on a 0–2 scale;
- per-bit `score0` and `score1` bars;
- score margin `abs(score1-score0)`;
- decoded binary/hex/ASCII representations;
- recording path, elapsed time, sample count, and serial health.

The reference implementation is:

- `capture.py`: serial acquisition;
- `plot_receiver.py`: offline Matplotlib visualization;
- `decode_tilde_message.py`: offline DSP and decoding;
- `live_receiver.py`: live Matplotlib frontend and automatic decode;
- `tests/test_receiver.py`: deterministic template/correlation tests.
