#!/usr/bin/env python3
"""Rocko beacon frame contract — the single source of truth for the receiver.

This module mirrors the frozen table in ``docs/equipment-codes.md`` and the
hardening-v2 spec exactly. It is deliberately dependency-light (numpy only) so
the decoder and its unit tests can import it without any serial or GUI code.

The numbers here MUST NOT be edited to "fix" a decode: the transmitter on the
Pi depends on the identical contract, so any change silently breaks the air
interface.

Frame layout (MSB-first, 12 bits total)::

    | 8 bits | Preamble | 01111110  (tilde "~", 0x7e)                      |
    | 4 bits | Flags    | bit3=fire  bit2=trapped  bit1=lost  bit0=injured |

Manchester mapping (matches the transmitter)::

    bit 1 -> tone,    no-tone   (ON,  OFF)
    bit 0 -> no-tone, tone      (OFF, ON)

Physical layer: 8 Hz square carrier, 1.0 s/bit (0.5 s half-symbols), emergency
frames repeat 3x with 3 s gaps, heartbeat ``0000`` auto every 120 s. Silence is
the alarm.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

# --- Frozen constants (do not change — see module docstring) -----------------

PREAMBLE_BITS: Tuple[int, ...] = (0, 1, 1, 1, 1, 1, 1, 0)  # "~" / 0x7e
FLAG_BITS: int = 4
FRAME_BITS: int = len(PREAMBLE_BITS) + FLAG_BITS  # 12

CARRIER_HZ: float = 8.0
BANDWIDTH_HZ: float = 2.0  # 7-9 Hz receiver passband
BIT_SECONDS: float = 1.0
HALF_SYMBOL_SECONDS: float = BIT_SECONDS / 2.0  # 0.5 s
HALF_SYMBOLS_PER_BIT: int = 2

REPEAT_COUNT: int = 3
REPEAT_GAP_SECONDS: float = 3.0
HEARTBEAT_PERIOD_SECONDS: float = 120.0

DEFAULT_SAMPLE_RATE_HZ: float = 200.0

# Flag bit -> weight, ordered MSB-first (fire is bit3, the most significant).
FLAG_WEIGHTS: Tuple[Tuple[str, int], ...] = (
    ("fire", 8),
    ("trapped", 4),
    ("lost", 2),
    ("injured", 1),
)

HEARTBEAT_CODE: str = "0000"
SOS_CODE: str = "1111"


def half_symbol_samples(sample_rate: float = DEFAULT_SAMPLE_RATE_HZ) -> int:
    """Samples in one Manchester half-symbol at the given sample rate."""
    return round(sample_rate * HALF_SYMBOL_SECONDS)


def manchester_levels(bits: Sequence[int]) -> np.ndarray:
    """Expand a bit sequence to its Manchester half-symbol gate.

    Regular OOK Manchester matching the transmitter contract:
    ``1 -> (ON, OFF)`` and ``0 -> (OFF, ON)``. Returns one 0/1 gate level per
    half-symbol (two per bit) as a float array.
    """
    return np.array(
        [level for bit in bits
         for level in ((1, 0) if bit else (0, 1))],
        dtype=float,
    )


def complex_template(
    bits: Sequence[int],
    half_samples: int,
    fs: float,
    carrier: float = CARRIER_HZ,
) -> np.ndarray:
    """Complex analytic template for a bit sequence.

    Each Manchester gate level is held for ``half_samples`` and modulated by a
    complex exponential at ``carrier``. OFF samples contribute zero energy.
    """
    gate = np.repeat(manchester_levels(bits), half_samples)
    time = np.arange(len(gate)) / fs
    return gate * np.exp(2j * np.pi * carrier * time)


def flags_to_event(flag_bits: Sequence[int]) -> Tuple[str, str]:
    """Map 4 flag bits (MSB-first: fire, trapped, lost, injured) to a label.

    Returns ``(label, code)`` where ``code`` is the 4-char binary nibble, e.g.
    ``("trapped+injured", "0101")``. ``0000`` is the heartbeat and ``1111`` is
    the dedicated SOS/help code (not the OR-combination of every flag).
    """
    bits = tuple(int(b) & 1 for b in flag_bits)
    if len(bits) != FLAG_BITS:
        raise ValueError(f"expected {FLAG_BITS} flag bits, got {len(bits)}")
    code = "".join(str(b) for b in bits)
    value = int(code, 2)
    if value == 0:
        return ("heartbeat", code)
    if value == 0b1111:
        return ("SOS", code)
    parts: List[str] = [name for name, weight in FLAG_WEIGHTS if value & weight]
    return ("+".join(parts), code)


def event_to_flags(label: str) -> Tuple[int, ...]:
    """Inverse of :func:`flags_to_event` for the named single/combo events.

    Accepts ``"heartbeat"``, ``"SOS"``, a single flag name, or a ``"a+b"``
    combination. Returns the 4 flag bits MSB-first. Used by the synthetic
    waveform generator in tests so intent is expressed by name, not by hand.
    """
    normalized = label.strip().lower()
    if normalized in ("heartbeat", "none", ""):
        return (0, 0, 0, 0)
    if normalized == "sos":
        return (1, 1, 1, 1)
    value = 0
    for part in normalized.split("+"):
        match = next((w for name, w in FLAG_WEIGHTS if name == part.strip()), None)
        if match is None:
            raise ValueError(f"unknown event component: {part!r}")
        value |= match
    return tuple(int(b) for b in f"{value:04b}")
