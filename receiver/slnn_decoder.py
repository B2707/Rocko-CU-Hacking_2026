#!/usr/bin/env python3
"""Optimal single-label decoder from Gültekin et al., arXiv:2503.18758.

The paper's Theorem 1 shows that an SLNN with no hidden layer and one output
per codeword is maximum-likelihood for equally likely BPSK codewords in AWGN:
its binary weight-matrix columns are the codewords and inference is ``r @ W``.
No training is required. Here the 28 Manchester matched-filter differences are
used as the real-valued soft input ``r``. This channel is not exactly BPSK/AWGN,
so the theorem's optimality guarantee does not transfer to our physical link.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import string
from typing import Sequence

import numpy as np

import coded_protocol as protocol


@dataclass(frozen=True)
class SLNNResult:
    scope: str
    header: int
    letter_byte: int
    letter: str
    coded_bits: tuple[int, ...]
    score: float
    runner_up_score: float
    margin: float
    expected_rank: int | None = None


@lru_cache(maxsize=1)
def alphabet_codebook() -> np.ndarray:
    """The 26 protocol-permitted ``~A`` through ``~Z`` output weights."""
    return np.stack(
        [protocol.encode_message(letter) for letter in string.ascii_uppercase]
    ).astype(np.float64)


@lru_cache(maxsize=1)
def full_linear_codebook() -> tuple[np.ndarray, np.ndarray]:
    """All 2^16 codewords of the complete linear (28,16) block code."""
    values = np.arange(1 << protocol.DATA_BITS, dtype=np.uint32)
    shifts = np.arange(protocol.DATA_BITS - 1, -1, -1, dtype=np.uint32)
    data = ((values[:, None] >> shifts) & 1).astype(np.int8)
    classes = (
        8 * data[:, 0::4] + 4 * data[:, 1::4]
        + 2 * data[:, 2::4] + data[:, 3::4]
    )
    codewords = protocol.GROUP_CODEBOOK[classes].reshape(-1, protocol.CODED_BITS)
    return values, codewords.astype(np.float64)


def soft_symbols(r0: Sequence[float], r1: Sequence[float]) -> np.ndarray:
    """Map Manchester half correlations to positive-for-one soft symbols."""
    first = np.asarray(r0, dtype=float)
    second = np.asarray(r1, dtype=float)
    if first.shape != (protocol.CODED_BITS,) or second.shape != first.shape:
        raise ValueError(f"expected two {protocol.CODED_BITS}-element observations")
    return first - second


def _rank(scores: np.ndarray, expected_index: int | None) -> int | None:
    if expected_index is None:
        return None
    # Competition ranking; ties share the same rank.
    return int(np.count_nonzero(scores > scores[expected_index]) + 1)


def _printable(value: int) -> str:
    return chr(value) if 32 <= value <= 126 else f"\\x{value:02x}"


def decode_alphabet(
    received: Sequence[float], expected_letter: str | None = None
) -> SLNNResult:
    """Run the protocol-restricted 28-input, 0-hidden, 26-output SLNN."""
    r = np.asarray(received, dtype=float)
    if r.shape != (protocol.CODED_BITS,):
        raise ValueError(f"expected {protocol.CODED_BITS} soft symbols")
    weights = alphabet_codebook()
    scores = weights @ r
    order = np.argsort(scores)[::-1]
    winner = int(order[0])
    expected_index = None
    if expected_letter is not None:
        expected_letter = expected_letter.upper()
        if len(expected_letter) != 1 or expected_letter not in string.ascii_uppercase:
            raise ValueError("expected letter must be A-Z")
        expected_index = string.ascii_uppercase.index(expected_letter)
    byte = ord(string.ascii_uppercase[winner])
    return SLNNResult(
        scope="alphabet-26",
        header=protocol.HEADER_BYTE,
        letter_byte=byte,
        letter=chr(byte),
        coded_bits=tuple(map(int, weights[winner])),
        score=float(scores[order[0]]),
        runner_up_score=float(scores[order[1]]),
        margin=float(scores[order[0]] - scores[order[1]]),
        expected_rank=_rank(scores, expected_index),
    )


def decode_full(
    received: Sequence[float], expected_value: int | None = None
) -> SLNNResult:
    """Run the literal 28-input, 0-hidden, 65,536-output linear-code SLNN."""
    r = np.asarray(received, dtype=float)
    if r.shape != (protocol.CODED_BITS,):
        raise ValueError(f"expected {protocol.CODED_BITS} soft symbols")
    values, weights = full_linear_codebook()
    scores = weights @ r
    order = np.argsort(scores)[::-1]
    winner = int(order[0])
    value = int(values[winner])
    expected_index = None
    if expected_value is not None:
        if not 0 <= expected_value < (1 << protocol.DATA_BITS):
            raise ValueError("expected value must be a 16-bit integer")
        expected_index = expected_value
    header, byte = value >> 8, value & 0xFF
    return SLNNResult(
        scope="linear-65536",
        header=header,
        letter_byte=byte,
        letter=_printable(byte),
        coded_bits=tuple(map(int, weights[winner])),
        score=float(scores[order[0]]),
        runner_up_score=float(scores[order[1]]),
        margin=float(scores[order[0]] - scores[order[1]]),
        expected_rank=_rank(scores, expected_index),
    )
