# Coded alphabet link protocol

The QNX transmitter sends two MSB-first bytes: header `~` (`01111110`) and a
capital letter `A` through `Z`. It advances one letter after every transmission.

Each four data bits are encoded as:

```text
[d1, d2, p1, d3, d4, p2, x]
p1 = d1 XOR d2
p2 = d3 XOR d4
x  = p1 XOR p2
```

Thus 16 data bits become four 7-bit groups, or 28 coded bits. Every coded bit
uses regular OOK Manchester at one second per bit:

```text
1 -> 8 Hz tone, then no tone
0 -> no tone, then 8 Hz tone
```

A complete transmission lasts 28 seconds. The coil is disabled for 15 seconds
between messages.

The receiver applies a fourth-order 7.25–8.75 Hz Butterworth bandpass and a Hilbert
transform, synchronizes against the encoded tilde, and evaluates five decoders:

- `naive-max`: larger Manchester half correlation per bit;
- `L1`: per-bit Gaussian likelihoods combined over valid 7-bit codewords;
- `L2`: two 3-bit parity-triplet Gaussian classifiers;
- `L3`: one 14-dimensional Gaussian classifier per valid 7-bit group;
- `L4`: normalized hybrid evidence from naive-max, L1, L2, and L3.

A layer succeeds only when it recovers header `~`, an uppercase ASCII letter,
and valid parity. The live analyzer displays every layer and identifies the
selected successful layer.
