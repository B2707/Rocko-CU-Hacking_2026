#!/usr/bin/env python3
"""Rocko beacon decoder — pure DSP, no serial or GUI.

This module turns a captured ``t,x,y`` waveform into a decoded beacon frame
using the frozen contract in :mod:`protocol`:

    1. median-centre each ADC channel and bandpass around the 8 Hz carrier;
    2. Hilbert transform to a complex analytic signal (phase-insensitive);
    3. slide the complex tilde-preamble template to find the frame start;
    4. score each of the 4 flag-bit windows against the Manchester 0/1
       templates and take the higher score (naive-max);
    5. map the 4 flags to an emergency label + 4-bit code.

Emergencies repeat 3x with 3 s gaps, so :func:`decode_repeats` finds every
repeat and majority-votes the flags for robustness. Everything here is a pure
function of numpy arrays: the unit tests drive it with synthetic waveforms and
never touch the Pico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy import signal

import protocol
from protocol import (
    BANDWIDTH_HZ,
    CARRIER_HZ,
    DEFAULT_SAMPLE_RATE_HZ,
    FLAG_BITS,
    FRAME_BITS,
    HALF_SYMBOL_SECONDS,
    HEARTBEAT_PERIOD_SECONDS,
    PREAMBLE_BITS,
    REPEAT_COUNT,
    REPEAT_GAP_SECONDS,
    complex_template,
    flags_to_event,
    manchester_levels,
)


@dataclass(frozen=True)
class DecodedFrame:
    """One decoded 12-bit frame."""

    start_index: int
    start_time: float
    sample_rate: float
    preamble_score: float
    flag_bits: Tuple[int, ...]
    code: str
    label: str
    bit_scores: Tuple[Tuple[float, float], ...]  # (score0, score1) per flag bit


@dataclass(frozen=True)
class RepeatDecode:
    """Consensus across one or more repeated frames of the same emergency."""

    flag_bits: Tuple[int, ...]
    code: str
    label: str
    frames: List[DecodedFrame] = field(default_factory=list)
    agreement: str = ""  # e.g. "3/3 frames agreed"


# --- DSP primitives ----------------------------------------------------------


def sample_rate_from_time(t: Sequence[float]) -> float:
    """Estimate the sample rate from the receiver timestamp column."""
    diffs = np.diff(np.asarray(t, dtype=float))
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if diffs.size == 0:
        raise ValueError("cannot derive sample rate: need >=2 increasing timestamps")
    return float(1.0 / np.median(diffs))


def bandpass_sos(fs: float, carrier: float = CARRIER_HZ, bandwidth: float = BANDWIDTH_HZ):
    """Fourth-order Butterworth bandpass SOS around the carrier."""
    low, high = carrier - bandwidth / 2.0, carrier + bandwidth / 2.0
    if low <= 0 or high >= fs / 2.0:
        raise ValueError(f"bandpass [{low:g}, {high:g}] Hz invalid for fs={fs:g} Hz")
    return signal.butter(4, [low, high], btype="bandpass", fs=fs, output="sos")


def analytic_channels(
    x: Sequence[float],
    y: Sequence[float],
    fs: float,
    carrier: float = CARRIER_HZ,
    bandwidth: float = BANDWIDTH_HZ,
) -> List[np.ndarray]:
    """Median-centre, zero-phase bandpass, and Hilbert each ADC channel."""
    sos = bandpass_sos(fs, carrier, bandwidth)
    channels = []
    for samples in (np.asarray(x, dtype=float), np.asarray(y, dtype=float)):
        filtered = signal.sosfiltfilt(sos, samples - np.median(samples))
        channels.append(signal.hilbert(filtered))
    return channels


def normalized_sliding_correlation(z: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Normalized correlation power of ``template`` slid across ``z`` (0..1)."""
    correlation = signal.fftconvolve(z, np.conj(template[::-1]), mode="valid")
    cumulative_energy = np.concatenate(([0.0], np.cumsum(np.abs(z) ** 2)))
    window_energy = cumulative_energy[len(template):] - cumulative_energy[:-len(template)]
    template_energy = np.vdot(template, template).real
    return np.abs(correlation) ** 2 / (template_energy * window_energy + 1e-15)


def template_score(channels: Sequence[np.ndarray], start: int, template: np.ndarray) -> float:
    """Summed normalized correlation of ``template`` at ``start`` over channels."""
    stop = start + len(template)
    template_energy = np.vdot(template, template).real
    score = 0.0
    for z in channels:
        segment = z[start:stop]
        segment_energy = np.vdot(segment, segment).real
        score += np.abs(np.vdot(template, segment)) ** 2 / (
            template_energy * segment_energy + 1e-15
        )
    return float(score)


# --- frame decoding ----------------------------------------------------------


def half_symbol_samples(fs: float) -> int:
    return round(fs * HALF_SYMBOL_SECONDS)


def preamble_correlation(
    channels: Sequence[np.ndarray], fs: float, carrier: float = CARRIER_HZ
) -> np.ndarray:
    """Two-channel summed correlation of the tilde preamble template (max 2)."""
    half = half_symbol_samples(fs)
    template = complex_template(PREAMBLE_BITS, half, fs, carrier)
    return sum(normalized_sliding_correlation(z, template) for z in channels)


def decode_flags_at(
    channels: Sequence[np.ndarray], start: int, fs: float, carrier: float = CARRIER_HZ
) -> Tuple[Tuple[int, ...], Tuple[Tuple[float, float], ...]]:
    """Decode the 4 flag bits that follow the preamble at ``start``."""
    half = half_symbol_samples(fs)
    bit_samples = 2 * half
    zero = complex_template([0], half, fs, carrier)
    one = complex_template([1], half, fs, carrier)
    total = len(channels[0])
    bits: List[int] = []
    scores: List[Tuple[float, float]] = []
    for index in range(FLAG_BITS):
        offset = start + (len(PREAMBLE_BITS) + index) * bit_samples
        if offset + bit_samples > total:
            raise ValueError(f"capture ends before flag bit {index}")
        score0 = template_score(channels, offset, zero)
        score1 = template_score(channels, offset, one)
        bits.append(int(score1 > score0))
        scores.append((score0, score1))
    return tuple(bits), tuple(scores)


def _frame_at(
    channels: Sequence[np.ndarray],
    t: np.ndarray,
    start: int,
    fs: float,
    carrier: float,
    peak: float,
) -> DecodedFrame:
    flag_bits, scores = decode_flags_at(channels, start, fs, carrier)
    label, code = flags_to_event(flag_bits)
    return DecodedFrame(
        start_index=int(start),
        start_time=float(t[start]),
        sample_rate=fs,
        preamble_score=float(peak),
        flag_bits=flag_bits,
        code=code,
        label=label,
        bit_scores=scores,
    )


def decode_frame(
    t: Sequence[float],
    x: Sequence[float],
    y: Sequence[float],
    carrier: float = CARRIER_HZ,
    bandwidth: float = BANDWIDTH_HZ,
) -> DecodedFrame:
    """Decode the single strongest frame in the capture."""
    t = np.asarray(t, dtype=float)
    fs = sample_rate_from_time(t)
    channels = analytic_channels(x, y, fs, carrier, bandwidth)
    correlation = preamble_correlation(channels, fs, carrier)
    start = int(np.argmax(correlation))
    return _frame_at(channels, t, start, fs, carrier, float(correlation[start]))


def find_frame_starts(
    correlation: np.ndarray,
    frame_samples: int,
    max_frames: int = REPEAT_COUNT,
    rel_threshold: float = 0.35,
) -> List[int]:
    """Pick up to ``max_frames`` correlation peaks at least ~half a frame apart."""
    working = correlation.astype(float).copy()
    peak = float(working.max())
    if peak <= 0:
        return [int(np.argmax(correlation))]
    guard = max(1, frame_samples // 2)
    starts: List[int] = []
    for _ in range(max_frames):
        index = int(np.argmax(working))
        if working[index] < rel_threshold * peak:
            break
        starts.append(index)
        lo, hi = max(0, index - guard), min(len(working), index + guard)
        working[lo:hi] = -np.inf
    return sorted(starts) if starts else [int(np.argmax(correlation))]


def consensus_flags(frames: Sequence[DecodedFrame]) -> Tuple[int, ...]:
    """Combine the flag bits of repeated frames into one fail-safe consensus.

    Per bit the value with the most votes wins. An *even* split (e.g. only two
    votable frames that disagree) is broken toward the stronger accumulated
    soft evidence — the summed ``(score0, score1)`` correlation across frames —
    never by ``round``. ``round`` is round-half-to-even, so an even tie collapses
    every tied bit to 0 and can manufacture a code (``0000``) matching *no*
    decoded frame.

    Fail-safe invariant: heartbeat ``0000`` is returned only when *every* decoded
    frame independently decoded ``0000``. If the vote lands on heartbeat while any
    frame carried an emergency bit, the best-synced frame (highest preamble
    score) wins instead. Rationale: a false emergency is a survivable false
    alarm, but a false heartbeat suppresses the "silence is the alarm" response —
    the worst possible failure of this device.
    """
    if not frames:
        raise ValueError("consensus_flags requires at least one frame")

    votes = np.array([frame.flag_bits for frame in frames], dtype=int)
    n_frames = len(frames)
    score0 = np.zeros(FLAG_BITS)
    score1 = np.zeros(FLAG_BITS)
    for frame in frames:
        for bit, (bit_score0, bit_score1) in enumerate(frame.bit_scores):
            score0[bit] += bit_score0
            score1[bit] += bit_score1

    consensus: List[int] = []
    for bit in range(FLAG_BITS):
        ones = int(votes[:, bit].sum())
        zeros = n_frames - ones
        if ones > zeros:
            consensus.append(1)
        elif zeros > ones:
            consensus.append(0)
        else:  # even split — trust the stronger correlation, never round()
            consensus.append(int(score1[bit] > score0[bit]))
    result = tuple(consensus)

    heartbeat = (0,) * FLAG_BITS
    if result == heartbeat and not all(frame.flag_bits == heartbeat for frame in frames):
        best = max(frames, key=lambda frame: frame.preamble_score)
        result = tuple(int(bit) for bit in best.flag_bits)
    return result


def decode_repeats(
    t: Sequence[float],
    x: Sequence[float],
    y: Sequence[float],
    carrier: float = CARRIER_HZ,
    bandwidth: float = BANDWIDTH_HZ,
    max_frames: int = REPEAT_COUNT,
) -> RepeatDecode:
    """Decode every repeated frame and majority-vote the flags.

    Falls back to a single frame when only one is present. The consensus is the
    per-bit majority across all decoded frames, which survives one corrupted
    repeat out of three.
    """
    t = np.asarray(t, dtype=float)
    fs = sample_rate_from_time(t)
    frame_samples = FRAME_BITS * 2 * half_symbol_samples(fs)
    if len(t) < frame_samples:
        raise ValueError(
            f"capture has {len(t)} samples; a complete frame requires {frame_samples}"
        )
    channels = analytic_channels(x, y, fs, carrier, bandwidth)
    correlation = preamble_correlation(channels, fs, carrier)

    frames: List[DecodedFrame] = []
    for start in find_frame_starts(correlation, frame_samples, max_frames):
        if start + frame_samples > len(channels[0]):
            continue
        frames.append(_frame_at(channels, t, start, fs, carrier, float(correlation[start])))

    if not frames:
        raise ValueError("no complete frame follows any detected preamble peak")

    consensus = consensus_flags(frames)
    label, code = flags_to_event(consensus)
    agreeing = sum(1 for frame in frames if frame.flag_bits == consensus)
    return RepeatDecode(
        flag_bits=consensus,
        code=code,
        label=label,
        frames=frames,
        agreement=f"{agreeing}/{len(frames)} frame(s) agreed",
    )


# --- synthetic waveform generator (tests + self-check, no hardware) ----------


def synthesize_capture(
    flags: Sequence[int],
    *,
    fs: float = DEFAULT_SAMPLE_RATE_HZ,
    carrier: float = CARRIER_HZ,
    repeats: int = 1,
    gap_seconds: float = REPEAT_GAP_SECONDS,
    lead_seconds: float = 2.0,
    tail_seconds: float = 3.0,
    amplitude: float = 1.0,
    dc: Tuple[float, float] = (1.60, 1.55),
    phase: Tuple[float, float] = (0.0, 0.6),
    channel_gain: Tuple[float, float] = (1.0, 0.8),
    noise_std: float = 0.0,
    seed: int = 0,
    corrupt_frame: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a realistic ``t,x,y`` capture for the given 4 flag bits.

    Produces a *real* OOK/Manchester waveform (what the ADC actually samples):
    ``dc + A*gain*gate*cos(2*pi*fc*t + phase) + noise`` on two channels with
    distinct DC, gain, and phase. ``repeats``/``gap_seconds`` model the 3x/3 s
    emergency repeats; ``corrupt_frame`` blanks one repeat's payload to exercise
    majority voting; ``noise_std`` adds Gaussian noise for the noisy test.
    """
    flag_bits = tuple(int(b) & 1 for b in flags)
    frame_bits = tuple(PREAMBLE_BITS) + flag_bits
    half = round(fs * HALF_SYMBOL_SECONDS)
    frame_gate = np.repeat(manchester_levels(frame_bits), half)
    gap = np.zeros(round(gap_seconds * fs))

    preamble_samples = len(PREAMBLE_BITS) * 2 * half
    segments = [np.zeros(round(lead_seconds * fs))]
    for repeat in range(repeats):
        gate = frame_gate.copy()
        if corrupt_frame is not None and repeat == corrupt_frame:
            # Invert the flag-region Manchester levels: the preamble still syncs
            # but the payload decodes to the complement flags, so this repeat is
            # a genuine outlier that majority voting must overrule.
            gate[preamble_samples:] = 1.0 - gate[preamble_samples:]
        segments.append(gate)
        if repeat != repeats - 1:
            segments.append(gap)
    segments.append(np.zeros(round(tail_seconds * fs)))

    gate_full = np.concatenate(segments)
    n = len(gate_full)
    t = np.arange(n) / fs
    rng = np.random.default_rng(seed)

    outputs = []
    for channel in range(2):
        tone = amplitude * channel_gain[channel] * gate_full * np.cos(
            2 * np.pi * carrier * t + phase[channel]
        )
        samples = dc[channel] + tone
        if noise_std:
            samples = samples + rng.normal(0.0, noise_std, size=n)
        outputs.append(samples)
    return t, outputs[0], outputs[1]


def _self_check() -> None:
    """Quick end-to-end sanity check runnable with ``python receiver/decoder.py``."""
    cases = {
        "fire": (1, 0, 0, 0),
        "trapped": (0, 1, 0, 0),
        "lost": (0, 0, 1, 0),
        "injured": (0, 0, 0, 1),
        "trapped+injured": (0, 1, 0, 1),
        "SOS": (1, 1, 1, 1),
        "heartbeat": (0, 0, 0, 0),
    }
    for expected_label, flags in cases.items():
        t, x, y = synthesize_capture(flags, noise_std=0.05, seed=1)
        result = decode_repeats(t, x, y)
        status = "ok" if result.flag_bits == flags else "FAIL"
        print(f"[{status}] {expected_label:16s} -> {result.label} ({result.code})")


if __name__ == "__main__":
    _self_check()
