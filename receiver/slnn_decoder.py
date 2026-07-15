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


@dataclass(frozen=True)
class CoherentSoftResult:
    symbols: np.ndarray
    weights: np.ndarray
    tone_coherence: float
    silence_coherence: float


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


def coherent_soft_symbols(
    channels: Sequence[np.ndarray], start: int, fs: float
) -> CoherentSoftResult:
    """Preamble-trained coherent combining of two already-filtered sensors.

    Complex carrier phasors are extracted from every Manchester half. The
    known encoded tilde identifies tone and silence halves. Their difference
    estimates the two-sensor channel vector, while silence halves estimate its
    noise covariance. Maximum-ratio weights combine sensor phase and amplitude
    before the paired-half differences are passed to the SLNN.
    """
    if len(channels) != 2:
        raise ValueError("coherent combining requires exactly two sensors")
    half = round(fs * protocol.HALF_SYMBOL_SECONDS)
    halves = 2 * protocol.CODED_BITS
    stop = start + halves * half
    values = [np.asarray(channel) for channel in channels]
    if start < 0 or any(len(channel) < stop for channel in values):
        raise ValueError("complete frame does not fit in filtered channels")
    carrier = np.exp(2j * np.pi * protocol.CARRIER_HZ * np.arange(half) / fs)
    phasors = np.empty((halves, 2), dtype=complex)
    for index in range(halves):
        offset = start + index * half
        for sensor, channel in enumerate(values):
            phasors[index, sensor] = (
                np.vdot(carrier, channel[offset:offset + half]) / np.sqrt(half)
            )

    header_gate = protocol.manchester_levels(protocol.ENCODED_HEADER).astype(bool)
    tone = phasors[:len(header_gate)][header_gate]
    silence = phasors[:len(header_gate)][~header_gate]
    tone_cov = tone.T @ tone.conj() / len(tone)
    # Prefer the true transmitter-off interval after the frame. Header OFF
    # halves contain coherent Butterworth ringing and are not pure noise.
    noise_start = stop + round(2.5 * fs)
    available_noise_halves = max(0, (len(values[0]) - noise_start) // half)
    noise_halves = min(20, available_noise_halves)  # central 10 s of the gap
    if noise_halves >= 4:
        noise_phasors = np.empty((noise_halves, 2), dtype=complex)
        for index in range(noise_halves):
            offset = noise_start + index * half
            for sensor, value in enumerate(values):
                noise_phasors[index, sensor] = (
                    np.vdot(carrier, value[offset:offset + half]) / np.sqrt(half)
                )
    else:
        noise_phasors = silence
    noise_cov = noise_phasors.T @ noise_phasors.conj() / len(noise_phasors)
    ridge = max(float(np.trace(noise_cov).real) / 2, 1e-12) * 1e-6
    noise_cov = noise_cov + ridge * np.eye(2)
    channel = tone.mean(axis=0) - silence.mean(axis=0)
    try:
        weights = np.linalg.solve(noise_cov, channel)
    except np.linalg.LinAlgError:
        weights = np.linalg.pinv(noise_cov) @ channel
    noise_scale = np.sqrt(max(float(np.vdot(weights, noise_cov @ weights).real), 1e-15))
    amplitude = np.abs(phasors @ weights.conj()) / noise_scale
    symbols = amplitude[0::2] - amplitude[1::2]

    def coherence(covariance: np.ndarray) -> float:
        denominator = float(covariance[0, 0].real * covariance[1, 1].real)
        return float(abs(covariance[0, 1]) ** 2 / max(denominator, 1e-15))

    return CoherentSoftResult(
        symbols=symbols,
        weights=weights,
        tone_coherence=coherence(tone_cov),
        silence_coherence=coherence(noise_cov),
    )


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
