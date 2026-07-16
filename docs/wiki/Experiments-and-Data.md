# Experiments and Data

## Persistent layout

```text
~/Desktop/CU-hakcing-captures/current-hamming/
├── raw/        immutable continuous t,x,y captures
├── manifests/  transmitter manifests, metadata, and logs
├── derived/    analysis tables, plots, and reports
└── models/     models fitted from designated training frames
```

Legacy material is preserved under `legacy-naive-bayes/` with SHA-256 checksums.
It can test the 8 Hz front end but predates the current Hamming/timing contract.

## Dataset rules

- Split by complete physical frame, never individual bits.
- Fit only on rows marked `train`.
- Do not inspect or tune against held-out letters before model fitting.
- Preserve raw captures unchanged; derived work goes elsewhere.
- Record transmitter UTC starts, requested duty, pulse statistics, distance,
  orientation, coil configuration, and environmental interventions.
- Use the central portion of the 15-second gap for H0/noise estimates.

## SNR definition

After applying the identical 7.25-8.75 Hz filter to frame and gap:

```text
Psignal = Pframe - Pnoise
SNR = 10 log10(Psignal / Pnoise)
```

If `Pframe <= Pnoise`, report no positive power estimate rather than inventing
an SNR. Duty is an experimental control; measured in-band SNR is ground truth.

## Reliable long capture

Use `receiver/capture.py` as the authoritative serial owner. It launches
`caffeinate` and is independent of a GUI window. Keep the laptop powered with
its lid open. A read-only growing-CSV viewer may be opened or closed without
affecting collection.
