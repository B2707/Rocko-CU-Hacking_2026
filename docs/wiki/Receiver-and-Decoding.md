# Receiver and Decoding

## Acquisition

The Pico sends `t,x,y` at 200 Hz. Validate rows, timestamp continuity, and ADC
clipping. Median-centre each sensor and apply the fourth-order 7.25-8.75 Hz
Butterworth bandpass. Complex analytic signals or equivalent I/Q matched
filters preserve carrier phase.

## Synchronization

Correlate both sensors against the Manchester waveform of the Hamming-encoded
tilde. Sum normalized correlation power across sensors. The current live
threshold is 0.8 on a two-channel 0-2 scale. Decoding with manifest-provided
start times can succeed below this threshold, but that is not autonomous
acquisition.

## Soft observations

For every coded bit, extract complex 8 Hz phasors from its first and second
one-second halves. Estimate the two-sensor channel `h` from known header tone
and silence halves. Estimate the noise covariance `R` from the central
transmitter-off gap.

The analytical coherent metric is:

```text
LLR_i = 2 Re{h^H R^-1 (z_first,i - z_second,i)}
```

GNB is an alternative learned bit-metric model, not a required preprocessing
stage before the analytical LLR.

## Experimental neural whitening

`duong_whitener.py` implements the gain-modulated recurrent circuit from Duong
et al. rather than a GRU trained by backpropagation. A fixed overcomplete frame
`W` is used while gains `g` adapt so the equilibrium response is
`y = [I + W diag(g) W^T]^-1 x`. The current implementation whitens instantaneous
four-dimensional real/imaginary sensor covariance; it does not guarantee
temporal independence. Adapt only on transmitter-off data and freeze during a
frame. Since it converges to symmetric/ZCA whitening, it must be compared with
ordinary ZCA and cannot be credited with a neural-specific benefit unless it
adapts better to changing contexts.

## Decoders

- naive-max: independent Manchester hard decisions.
- L1: bit Gaussian evidence summed over legal Hamming words.
- L2: Gaussian evidence over overlapping parity checks.
- L3: complete seven-bit-group Gaussian classification.
- L4: normalized hybrid of L1/L2/L3 and matched energy.
- SLNN: fixed codebook-weight maximum-likelihood scorer; no training.

The restricted SLNN always chooses one of A-Z, so it is never sufficient proof
of detection. Compare it with the unrestricted 65,536-word decoder.

## Acceptance

Operational acceptance should require synchronization, no clipping, a valid
unrestricted `~` plus uppercase payload, restricted/unrestricted agreement,
adequate margin, and an H0/no-transmission test calibrated from silent gaps.
Hamming validity alone is not rejection because codebook decoding always emits
a legal Hamming word.
