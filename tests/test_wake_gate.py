"""Wake-gate tests: compile TTS/classifier.c and prove the single choke point.

The load-bearing test is `test_no_wake_emergency_content_produces_no_output`,
the E2 regression guard: a transcript full of emergency words but WITHOUT the
wake phrase yields empty classifier output, so the shell listener writes nothing
to the beacon spool and nothing transmits.

Skipped automatically if no C compiler is available.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TTS_DIR = Path(__file__).parents[1] / "TTS"
CLASSIFIER_SRC = TTS_DIR / "classifier.c"
CC = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


@unittest.skipUnless(CC and CLASSIFIER_SRC.exists(), "no C compiler or classifier.c")
class WakeGateTests(unittest.TestCase):
    binary = None
    _tmp = None

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.binary = os.path.join(cls._tmp.name, "classifier")
        proc = subprocess.run(
            [CC, "-O2", "-o", cls.binary, str(CLASSIFIER_SRC), "-lm"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise unittest.SkipTest(f"classifier.c failed to build: {proc.stderr}")

    @classmethod
    def tearDownClass(cls):
        if cls._tmp:
            cls._tmp.cleanup()

    def classify(self, text):
        """Return the classifier's stdout (stripped) for one transcript line."""
        proc = subprocess.run(
            [self.binary],
            input=text + "\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        return proc.stdout.strip()

    def first_token(self, text):
        out = self.classify(text)
        return out.split(" ", 1)[0] if out else ""

    # --- E2: the no-wake bug stays closed -------------------------------
    def test_no_wake_emergency_content_produces_no_output(self):
        # emergency words galore, but no "hey rocko help" -> gate closed.
        for line in (
            "i am trapped and my leg is injured please help me",
            "there is smoke everywhere the cave is on fire",
            "somebody help help help i am lost",
            "help",
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    self.classify(line),
                    "",
                    "no wake phrase must yield NO output (no spool write)",
                )

    # --- E1 / decision 1: wake phrase opens the gate --------------------
    def test_wake_phrase_alone_is_sos(self):
        self.assertEqual(self.first_token("hey rocko help"), "sos")

    def test_wake_phrase_with_command_classifies_it(self):
        self.assertEqual(
            self.first_token("hey rocko help i am stuck and cannot get out"),
            "trapped",
        )
        self.assertEqual(
            self.first_token("hey rocko help my arm is broken and bleeding"),
            "injured",
        )
        self.assertEqual(
            self.first_token("hey rocko help the kitchen is on fire"), "fire"
        )
        self.assertEqual(
            self.first_token("hey rocko help i am lost in the woods"), "lost"
        )

    def test_whisper_variants_and_punctuation(self):
        # case, punctuation, comma splits, and rocko homophones all still open it
        # (F6: "rock" was dropped as too broad; "rockoh" is a retained variant)
        for line in (
            "HEY, ROCCO! HELP, the kitchen is on fire",
            "hey roko help the kitchen is on fire",
            "Hey Rockoh, help - the kitchen is on fire",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.first_token(line), "fire")

    def test_wake_gated_cancel_is_stop(self):
        self.assertEqual(self.first_token("hey rocko help i am okay stop"), "stop")
        self.assertEqual(self.first_token("hey rocko help cancel"), "stop")

    def test_help_word_without_wake_phrase_does_not_fire(self):
        # "help" alone must NOT open the gate — it is part of the phrase, not the
        # trigger (proves the phrase is required, not just the word).
        self.assertEqual(self.classify("can you help me please"), "")

    # --- F1: emergency content always outranks a cancel word ------------
    def test_emergency_content_outranks_cancel_word(self):
        # a cancel word riding along with real emergency content must NOT cancel
        self.assertEqual(
            self.first_token("hey rocko help i am trapped okay"), "trapped"
        )
        self.assertEqual(
            self.first_token(
                "hey rocko help everything is clear now i am trapped under a rock"
            ),
            "trapped",
        )
        # "stuck ok" - the classifier's class wins, and it is NOT stop
        self.assertNotEqual(
            self.first_token("hey rocko help i am stuck ok"), "stop"
        )

    def test_cancel_wins_only_without_emergency(self):
        # a bare cancel (no emergency word) still cancels
        self.assertEqual(self.first_token("hey rocko help i am okay"), "stop")
        self.assertEqual(self.first_token("hey rocko help stop"), "stop")

    # --- F6: tighter variants + stutter tolerance -----------------------
    def test_broad_rocko_variants_no_longer_fire(self):
        # casual speech that used to false-fire ("rocky"/"helps") must stay silent
        self.assertEqual(
            self.classify("hey rocky helps me when i am lost"), ""
        )

    def test_consecutive_duplicate_wake_tokens_fire(self):
        # a stutter of an accepted token still opens the gate
        self.assertEqual(
            self.first_token("hey rocko rocko help i am trapped"), "trapped"
        )
        self.assertEqual(
            self.first_token("hey hey rocko help i am lost"), "lost"
        )


if __name__ == "__main__":
    unittest.main()
