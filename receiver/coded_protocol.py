#!/usr/bin/env python3
"""Two-byte Manchester/parity protocol shared by receiver tooling.

Payload is two MSB-first bytes: tilde header (0x7e) and one capital ASCII
letter. Every four data bits become seven coded bits:
[d1,d2,d1^d2,d3,d4,d3^d4,(d1^d2)^(d3^d4)].
"""

from __future__ import annotations

from typing import Sequence
import numpy as np

HEADER_BYTE = 0x7E
CARRIER_HZ = 8.0
BANDWIDTH_HZ = 1.5  # tight 7.25-8.75 Hz passband; preserves Manchester edges
BIT_SECONDS = 1.0
HALF_SYMBOL_SECONDS = 0.5
DEFAULT_SAMPLE_RATE_HZ = 200.0
DATA_BYTES = 2
DATA_BITS = 16
GROUP_DATA_BITS = 4
GROUP_CODED_BITS = 7
GROUPS = DATA_BITS // GROUP_DATA_BITS
CODED_BITS = GROUPS * GROUP_CODED_BITS
INTERFRAME_GAP_SECONDS = 15.0

GROUP_CODEBOOK = np.array([
    [a, b, a ^ b, c, d, c ^ d, (a ^ b) ^ (c ^ d)]
    for a in (0, 1) for b in (0, 1) for c in (0, 1) for d in (0, 1)
], dtype=np.int8)
GROUP_DATA = GROUP_CODEBOOK[:, [0, 1, 3, 4]]
TRIPLET_CODEBOOK = np.array(
    [[a, b, a ^ b] for a in (0, 1) for b in (0, 1)], dtype=np.int8
)


def byte_bits(value: int) -> tuple[int, ...]:
    if not 0 <= value <= 255:
        raise ValueError("byte must be in range 0..255")
    return tuple((value >> shift) & 1 for shift in range(7, -1, -1))


def bits_byte(bits: Sequence[int]) -> int:
    if len(bits) != 8:
        raise ValueError("exactly eight bits required")
    value = 0
    for bit in bits:
        value = (value << 1) | (int(bit) & 1)
    return value


def encode_data_bits(data_bits: Sequence[int]) -> np.ndarray:
    data = np.asarray(data_bits, dtype=np.int8)
    if len(data) % GROUP_DATA_BITS:
        raise ValueError("data length must be a multiple of four")
    classes = 8 * data[0::4] + 4 * data[1::4] + 2 * data[2::4] + data[3::4]
    return GROUP_CODEBOOK[classes].reshape(-1)


def encode_message(letter: str) -> np.ndarray:
    if len(letter) != 1 or not "A" <= letter <= "Z":
        raise ValueError("letter must be one uppercase ASCII character A-Z")
    data = byte_bits(HEADER_BYTE) + byte_bits(ord(letter))
    return encode_data_bits(data)


def data_from_groups(classes: Sequence[int]) -> np.ndarray:
    return GROUP_DATA[np.asarray(classes, dtype=int)].reshape(-1)


def decode_bytes_from_classes(classes: Sequence[int]) -> tuple[int, int]:
    data = data_from_groups(classes)
    if len(data) != DATA_BITS:
        raise ValueError(f"expected {GROUPS} groups")
    return bits_byte(data[:8]), bits_byte(data[8:16])


def parity_valid(coded: Sequence[int]) -> bool:
    bits = np.asarray(coded, dtype=np.int8)
    if len(bits) != CODED_BITS:
        return False
    groups = bits.reshape(GROUPS, GROUP_CODED_BITS)
    for group in groups:
        d1, d2, p1, d3, d4, p2, x = map(int, group)
        if p1 != (d1 ^ d2) or p2 != (d3 ^ d4) or x != (p1 ^ p2):
            return False
    return True


def manchester_levels(bits: Sequence[int]) -> np.ndarray:
    return np.array(
        [level for bit in bits for level in ((1, 0) if bit else (0, 1))],
        dtype=float,
    )


def complex_template(bits: Sequence[int], half_samples: int, fs: float) -> np.ndarray:
    gate = np.repeat(manchester_levels(bits), half_samples)
    time = np.arange(len(gate)) / fs
    return gate * np.exp(2j * np.pi * CARRIER_HZ * time)


ENCODED_HEADER = encode_data_bits(byte_bits(HEADER_BYTE))
