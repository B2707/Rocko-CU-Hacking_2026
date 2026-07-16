# Hamming Alphabet Protocol

## Frame construction

Two data bytes are sent MSB-first:

1. Header `~` = `0x7E`.
2. One uppercase letter `A` through `Z`.

Each four-bit nibble `[d1,d2,d3,d4]` becomes:

```text
[p1,p2,d1,p4,d2,d3,d4]
p1 = d1 XOR d2 XOR d4
p2 = d1 XOR d3 XOR d4
p4 = d2 XOR d3 XOR d4
```

Sixteen data bits therefore become 28 coded bits. Hamming(7,4) has minimum
distance three and corrects one hard-bit error per group under its standard
assumptions.

## Modulation

```text
coded 1 -> 1 s 8 Hz tone, then 1 s silence
coded 0 -> 1 s silence, then 1 s 8 Hz tone
```

- Coded bit rate: 0.5 bit/s.
- Frame duration: 56 seconds.
- Interframe transmitter-off gap: 15 seconds.

The encoded tilde occupies the first 14 coded bits and is the synchronization
preamble. Old pairwise-code or one-bit/s captures are not end-to-end compatible
with this protocol.
