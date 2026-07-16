# Rocko Cave-Beacon Wiki

Rocko is a low-frequency magnetic cave-beacon link. A QNX Raspberry Pi drives
an L298N/coil transmitter; a Pico streams two 12-bit magnetic-sensor channels
to a Mac receiver at 200 Hz.

## Current protocol

- Message: MSB-first `~` (`0x7E`) plus one uppercase ASCII letter.
- Error correction: four standard even-parity Hamming(7,4) groups.
- Frame: 28 coded bits, 56 seconds.
- Modulation: 8 Hz OOK Manchester, one second per half-symbol.
- Gap: 15 seconds with the transmitter disabled.

## Pages

- [Hardware](Hardware.md)
- [Protocol](Protocol.md)
- [Transmitter](Transmitter.md)
- [Receiver and decoding](Receiver-and-Decoding.md)
- [Experiments and data](Experiments-and-Data.md)
- [Latest benchmark](Results-2026-07-16.md)
- [Operations and troubleshooting](Operations-and-Troubleshooting.md)
- [Context handoff](Context-Handoff.md)

## Canonical repositories and data

- Persistent worktree: `~/Desktop/CU-hakcing-2026`
- Persistent artifacts: `~/Desktop/CU-hakcing-captures`
- Branch: `task/receiver-v2`
- Remote: `B2707/Rocko-CU-Hacking_2026`

Never use `/tmp` as the primary worktree or the only copy of experimental data.
