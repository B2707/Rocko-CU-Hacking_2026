"""Photo classifier tests: pure helpers + graceful-degrade paths.

No tflite/PIL needed — the heavy deps are imported lazily inside the module, so
the model-missing and labels/rank/label-loading paths run everywhere. The real
inference is verified on the Pi (see photo/README.md).
"""

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "photo" / "photo_classify.py"
SPEC = importlib.util.spec_from_file_location("photo_classify", MODULE_PATH)
photo = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = photo
assert SPEC.loader is not None
SPEC.loader.exec_module(photo)


class LabelAndRankTests(unittest.TestCase):
    def test_load_labels_ignores_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "labels.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Abrasions\n\nBruises\n  \nBurns\n")
            self.assertEqual(photo.load_labels(path), ["Abrasions", "Bruises", "Burns"])

    def test_rank_orders_top_k_highest_first(self):
        labels = ["a", "b", "c", "d"]
        probs = [0.1, 0.7, 0.05, 0.15]
        ranked = photo.rank(probs, labels, k=3)
        self.assertEqual([lbl for lbl, _ in ranked], ["b", "d", "a"])
        self.assertAlmostEqual(ranked[0][1], 0.7)
        self.assertEqual(len(ranked), 3)

    def test_rank_matches_labels_by_index(self):
        labels = ["Abrasions", "Bruises", "Burns", "Normal"]
        probs = [0.02, 0.93, 0.03, 0.02]  # bruise.jpg-shaped
        top_label, top_p = photo.rank(probs, labels, k=1)[0]
        self.assertEqual(top_label, "Bruises")
        self.assertAlmostEqual(top_p, 0.93)


class GracefulDegradeTests(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = photo.main(argv)
        return rc, buf.getvalue()

    def test_missing_model_reports_not_installed(self):
        rc, out = self._run(["--model", "/no/such.tflite", "--labels", "/no/l.txt"])
        self.assertEqual(rc, 3)
        self.assertIn("not installed yet", out)
        self.assertNotIn("Traceback", out)

    def test_missing_labels_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = os.path.join(tmp, "injury.tflite")
            Path(model).write_bytes(b"not a real model")  # exists, so we reach labels check
            rc, out = self._run(["x.jpg", "--model", model, "--labels", "/no/l.txt"])
        self.assertEqual(rc, 3)
        self.assertIn("labels file missing", out)

    def test_missing_image_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = os.path.join(tmp, "injury.tflite")
            labels = os.path.join(tmp, "labels.txt")
            Path(model).write_bytes(b"stub")
            Path(labels).write_text("Abrasions\nBruises\n", encoding="utf-8")
            rc, out = self._run(["/no/photo.jpg", "--model", model, "--labels", labels])
        self.assertEqual(rc, 2)
        self.assertIn("photo not found", out)


if __name__ == "__main__":
    unittest.main()
