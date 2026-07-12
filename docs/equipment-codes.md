# Beacon Frame — flags contract (12 bits)

> **FROZEN 2026-07-12 (hardening v2, PR #9).** The payload is 4 **condition
> flags** that OR together, behind a tilde preamble. This table is the interface
> between the AI code (classifier), the frame encoder
> (`transmitter/transmitter.py`), and the surface decoder — change it only by
> telling everyone. The bits, preamble, modulation, timing, repeat counts, and
> heartbeat period are the agreed contract (decision 4); hardening v2 only ADDS
> logging, naming, and robustness around it.

## Frame layout (MSB first, ~12 s on air)

| Bits | Field | Value |
|------|----------|-------|
| 8 | Preamble | `01111110` (tilde) |
| 4 | Flags | `bit3=fire  bit2=trapped  bit1=lost  bit0=injured` |

## Flag values

| Flags | Meaning | Trigger |
|-------|-------------------------|---------------------------------------|
| 0000 | Heartbeat — alive, no emergency | sent automatically every 120 s |
| 1000 | Fire | classifier class `fire` |
| 0100 | Trapped | classifier class `trapped` |
| 0010 | Lost | classifier class `lost` |
| 0001 | Injured | classifier class `injured` |
| 1111 | SOS / help | wake phrase said alone, or `[help]` keyword override |
| any other | Combination (flags OR together) | multiple triggers, e.g. 0101 = trapped+injured |

Classifier class `none` never triggers a transmission.

## Log-line convention (E4)

Every log or banner line that names an emergency carries its 4-bit code in
parentheses, so the AI side and the signals side always read the same thing:

```
injured (0001)
SOS (1111)
trapped+injured (0101)
heartbeat (0000)
```

## Physical layer (so both sides stay honest)

- Tone = 8 Hz square via IN3/IN4 polarity flips (62.5 ms per half-cycle),
  ENB gates on/off. Coil on L298N OUT3/OUT4.
- Regular Manchester per bit: `1 -> tone/no-tone`, `0 -> no-tone/tone`.
- Bit time 1.0 s (0.5 s half-symbols → 4 carrier cycles per tone half).
- Emergency frames repeat 3× with 3 s gaps, then heartbeat resumes.
- Silence is the alarm: if heartbeats stop arriving, the surface raises it.
- Wiring (BCM): GPIO22 → IN3, GPIO17 → IN4, GPIO27 → ENB, coil on OUT3/OUT4.
</content>
