import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path(__file__).parents[1] / "receiver" / "decode_tilde_message.py"
SPEC = importlib.util.spec_from_file_location("receiver_decoder", MODULE_PATH)
decoder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = decoder
assert SPEC.loader is not None
SPEC.loader.exec_module(decoder)


class ManchesterTemplateTests(unittest.TestCase):
    def test_regular_manchester_levels(self):
        np.testing.assert_array_equal(
            decoder.manchester_levels([0, 1, 1, 0]),
            [0, 1, 1, 0, 1, 0, 0, 1],
        )

    def test_tilde_template_correlation_finds_message_start(self):
        fs = 40.0
        half_samples = 20
        carrier = 8.0
        tilde = [0, 1, 1, 1, 1, 1, 1, 0]
        template = decoder.complex_template(tilde, half_samples, fs, carrier)
        prefix_samples = 73
        analytic_signal = np.concatenate(
            [np.zeros(prefix_samples, dtype=complex), template, np.zeros(91, dtype=complex)]
        )

        correlation = decoder.normalized_sliding_correlation(analytic_signal, template)

        self.assertEqual(int(np.argmax(correlation)), prefix_samples)
        self.assertAlmostEqual(float(np.max(correlation)), 1.0, places=10)

    def test_naive_max_selects_correct_bit_templates(self):
        fs = 40.0
        half_samples = 20
        carrier = 8.0
        zero = decoder.complex_template([0], half_samples, fs, carrier)
        one = decoder.complex_template([1], half_samples, fs, carrier)
        channels = [one.copy(), 0.7 * one]

        zero_score = decoder.template_score(channels, 0, zero)
        one_score = decoder.template_score(channels, 0, one)

        self.assertGreater(one_score, zero_score)
        self.assertAlmostEqual(one_score, 2.0, places=10)


if __name__ == "__main__":
    unittest.main()
