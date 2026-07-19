"""Receiver decoder tests — decode synthetic beacon waveforms, no hardware.

Every test synthesizes a real OOK/Manchester ``t,x,y`` waveform with
``decoder.synthesize_capture`` and runs the full decode pipeline. Nothing here
opens a serial port, so the whole suite runs on any laptop with numpy + scipy.

Run:  python -m pytest tests/          (or)  python -m unittest discover tests
"""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

RECEIVER_DIR = Path(__file__).parents[1] / "receiver"
if str(RECEIVER_DIR) not in sys.path:
    sys.path.insert(0, str(RECEIVER_DIR))

import protocol  # noqa: E402
import decoder  # noqa: E402
import eventlog  # noqa: E402


class ContractTests(unittest.TestCase):
    """The frozen frame contract must never drift."""

    def test_preamble_is_the_tilde(self):
        self.assertEqual(protocol.PREAMBLE_BITS, (0, 1, 1, 1, 1, 1, 1, 0))

    def test_timing_constants(self):
        self.assertEqual(protocol.CARRIER_HZ, 8.0)
        self.assertEqual(protocol.BIT_SECONDS, 1.0)
        self.assertEqual(protocol.HALF_SYMBOL_SECONDS, 0.5)
        self.assertEqual(protocol.FRAME_BITS, 12)
        self.assertEqual(protocol.REPEAT_COUNT, 3)
        self.assertEqual(protocol.REPEAT_GAP_SECONDS, 3.0)
        self.assertEqual(protocol.HEARTBEAT_PERIOD_SECONDS, 120.0)

    def test_manchester_mapping_matches_contract(self):
        # 1 -> tone,no-tone (ON,OFF); 0 -> no-tone,tone (OFF,ON)
        np.testing.assert_array_equal(protocol.manchester_levels([1]), [1, 0])
        np.testing.assert_array_equal(protocol.manchester_levels([0]), [0, 1])

    def test_flag_bit_assignment(self):
        self.assertEqual(protocol.flags_to_event((1, 0, 0, 0)), ("fire", "1000"))
        self.assertEqual(protocol.flags_to_event((0, 1, 0, 0)), ("trapped", "0100"))
        self.assertEqual(protocol.flags_to_event((0, 0, 1, 0)), ("lost", "0010"))
        self.assertEqual(protocol.flags_to_event((0, 0, 0, 1)), ("injured", "0001"))
        self.assertEqual(protocol.flags_to_event((0, 0, 0, 0)), ("heartbeat", "0000"))
        self.assertEqual(protocol.flags_to_event((1, 1, 1, 1)), ("SOS", "1111"))
        self.assertEqual(protocol.flags_to_event((0, 1, 0, 1)), ("trapped+injured", "0101"))


class DecodeSingleFlagTests(unittest.TestCase):
    """Each single emergency flag decodes from a clean synthetic waveform."""

    def _decode(self, flags, **kwargs):
        t, x, y = decoder.synthesize_capture(flags, seed=7, **kwargs)
        return decoder.decode_repeats(t, x, y)

    def test_fire(self):
        result = self._decode((1, 0, 0, 0))
        self.assertEqual(result.flag_bits, (1, 0, 0, 0))
        self.assertEqual((result.label, result.code), ("fire", "1000"))

    def test_trapped(self):
        result = self._decode((0, 1, 0, 0))
        self.assertEqual((result.label, result.code), ("trapped", "0100"))

    def test_lost(self):
        result = self._decode((0, 0, 1, 0))
        self.assertEqual((result.label, result.code), ("lost", "0010"))

    def test_injured(self):
        result = self._decode((0, 0, 0, 1))
        self.assertEqual((result.label, result.code), ("injured", "0001"))

    def test_sos(self):
        result = self._decode((1, 1, 1, 1))
        self.assertEqual((result.label, result.code), ("SOS", "1111"))


class DecodeComboAndHeartbeatTests(unittest.TestCase):
    def test_combination_flags_or_together(self):
        t, x, y = decoder.synthesize_capture((0, 1, 0, 1), seed=11)
        result = decoder.decode_repeats(t, x, y)
        self.assertEqual(result.flag_bits, (0, 1, 0, 1))
        self.assertEqual((result.label, result.code), ("trapped+injured", "0101"))

    def test_heartbeat_all_zero(self):
        t, x, y = decoder.synthesize_capture((0, 0, 0, 0), seed=13)
        result = decoder.decode_repeats(t, x, y)
        self.assertEqual(result.flag_bits, (0, 0, 0, 0))
        self.assertEqual((result.label, result.code), ("heartbeat", "0000"))


class DecodeNoisyTests(unittest.TestCase):
    def test_noisy_capture_still_decodes(self):
        # Heavy Gaussian noise on both channels; the coherent template gain
        # still recovers the flags. Checked across several seeds for stability.
        for seed in range(8):
            t, x, y = decoder.synthesize_capture(
                (0, 1, 0, 1), noise_std=0.25, seed=seed
            )
            result = decoder.decode_repeats(t, x, y)
            self.assertEqual(
                result.flag_bits, (0, 1, 0, 1), msg=f"failed at seed {seed}"
            )

    def test_incomplete_frame_is_rejected_cleanly(self):
        # A short startup burst must not become an analyzer error halfway
        # through flag decoding; it is rejected before DSP frame selection.
        samples = int(protocol.DEFAULT_SAMPLE_RATE_HZ * 5)
        t = np.arange(samples) / protocol.DEFAULT_SAMPLE_RATE_HZ
        x = np.ones(samples)
        y = np.ones(samples)
        with self.assertRaisesRegex(ValueError, "complete frame requires"):
            decoder.decode_repeats(t, x, y)

    def test_majority_vote_overrules_one_corrupted_repeat(self):
        # 3x emergency repeats, the middle one deliberately inverted. Per-bit
        # majority voting must still land on the true flags.
        t, x, y = decoder.synthesize_capture(
            (1, 0, 0, 0), repeats=3, corrupt_frame=1, noise_std=0.1, seed=3
        )
        result = decoder.decode_repeats(t, x, y)
        self.assertEqual(result.flag_bits, (1, 0, 0, 0))
        self.assertEqual(len(result.frames), 3)
        self.assertIn("2/3", result.agreement)


class DspPrimitiveTests(unittest.TestCase):
    """Low-level correlation behaviour (kept from the original suite)."""

    def test_tilde_template_correlation_finds_message_start(self):
        fs, half, carrier = 40.0, 20, 8.0
        tilde = protocol.PREAMBLE_BITS
        template = protocol.complex_template(tilde, half, fs, carrier)
        prefix = 73
        analytic = np.concatenate(
            [np.zeros(prefix, dtype=complex), template, np.zeros(91, dtype=complex)]
        )
        correlation = decoder.normalized_sliding_correlation(analytic, template)
        self.assertEqual(int(np.argmax(correlation)), prefix)
        self.assertAlmostEqual(float(np.max(correlation)), 1.0, places=10)

    def test_naive_max_selects_correct_bit_template(self):
        fs, half, carrier = 40.0, 20, 8.0
        zero = protocol.complex_template([0], half, fs, carrier)
        one = protocol.complex_template([1], half, fs, carrier)
        channels = [one.copy(), 0.7 * one]
        self.assertGreater(
            decoder.template_score(channels, 0, one),
            decoder.template_score(channels, 0, zero),
        )
        self.assertAlmostEqual(decoder.template_score(channels, 0, one), 2.0, places=10)


def _frame(flags, preamble=2.0):
    """Build a DecodedFrame with soft scores consistent with its hard bits."""
    flags = tuple(int(b) for b in flags)
    label, code = protocol.flags_to_event(flags)
    scores = tuple((0.2, 1.9) if b else (1.9, 0.2) for b in flags)
    return decoder.DecodedFrame(
        start_index=0, start_time=0.0, sample_rate=200.0,
        preamble_score=preamble, flag_bits=flags, code=code,
        label=label, bit_scores=scores,
    )


class ConsensusVoteTests(unittest.TestCase):
    """Majority voting must never manufacture a false heartbeat (finding: high)."""

    def test_even_split_never_decodes_a_phantom_heartbeat(self):
        # fire + a corrupted repeat that decoded as trapped: two votable frames
        # that disagree. round(mean) used to collapse this to 0000 (heartbeat),
        # a code matching NEITHER frame. Consensus must be a real frame.
        frames = [_frame((1, 0, 0, 0), preamble=2.0), _frame((0, 1, 0, 0), preamble=1.5)]
        consensus = decoder.consensus_flags(frames)
        self.assertNotEqual(consensus, (0, 0, 0, 0))
        self.assertIn(consensus, {(1, 0, 0, 0), (0, 1, 0, 0)})
        # Tie-break follows the stronger preamble (fire), never round-to-even.
        self.assertEqual(consensus, (1, 0, 0, 0))

    def test_heartbeat_requires_unanimous_zero(self):
        # Two heartbeat-looking frames + one injured: majority computes 0000, but
        # a frame carried an emergency bit, so the best-synced frame wins instead.
        frames = [
            _frame((0, 0, 0, 0), preamble=1.0),
            _frame((0, 0, 0, 0), preamble=1.0),
            _frame((0, 0, 0, 1), preamble=2.0),
        ]
        consensus = decoder.consensus_flags(frames)
        self.assertNotEqual(consensus, (0, 0, 0, 0))
        self.assertEqual(consensus, (0, 0, 0, 1))

    def test_unanimous_heartbeat_is_allowed(self):
        frames = [_frame((0, 0, 0, 0)) for _ in range(3)]
        self.assertEqual(decoder.consensus_flags(frames), (0, 0, 0, 0))

    def test_clear_majority_still_wins(self):
        frames = [_frame((1, 0, 0, 0)), _frame((1, 0, 0, 0)), _frame((0, 1, 0, 0))]
        self.assertEqual(decoder.consensus_flags(frames), (1, 0, 0, 0))

    def test_two_frame_emergency_downgrade_repro(self):
        # End-to-end: a fresh SOS transmission caught as an even number of votable
        # frames must not silently become heartbeat via the vote.
        t, x, y = decoder.synthesize_capture((1, 1, 1, 1), repeats=2, seed=5)
        result = decoder.decode_repeats(t, x, y)
        self.assertNotEqual(result.flag_bits, (0, 0, 0, 0))


class EventLogRobustnessTests(unittest.TestCase):
    """A closed log handle must never raise out of emit (finding: high)."""

    def test_emit_after_close_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = eventlog.EventLog(Path(tmp) / "rocko.log")
            log.emit("DECODE", "fire (1000)", echo=False)
            log.close()
            log.close()  # idempotent second close (mirrors double-shutdown paths)
            # Writing to the now-closed handle must be swallowed, not crash.
            event = log.emit("CAPTURE", "stopped — saved capture", echo=False)
            self.assertEqual(event.kind, "CAPTURE")
            self.assertEqual(event.number, 2)


if __name__ == "__main__":
    unittest.main()
