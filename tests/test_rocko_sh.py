"""rocko.sh launcher regression tests (POSIX sh behavior).

These guard the shell-side hardening fixes that a `sh -n` parse check cannot:
  - F2:  `rocko.sh` with no args reaches the startup path (a bare zero-arg
         `shift` used to abort the whole script under ksh/dash).
  - F13: startup failures exit nonzero; `rocko.sh photo` propagates the
         classifier's exit code through the numbering pipe.
  - F15: a stale rocko.pid alongside a live transmitter pidfile prints the
         exact recovery commands and refuses cleanly (nonzero).

Run under dash when available (the shell whose special-builtin semantics
exposed the F2 bug); otherwise fall back to /bin/sh. Skipped only if neither
runs. The default deployment paths do not exist off the Pi, so every run fails
fast at "transmitter not found" - exactly the startup path we want to exercise.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).parents[1]
ROCKO = REPO / "rocko.sh"
SHELL = shutil.which("dash") or shutil.which("sh")


@unittest.skipUnless(SHELL and ROCKO.exists(), "no POSIX shell or rocko.sh")
class RockoLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _env(self, **extra):
        env = dict(os.environ)
        # keep every stateful path inside the temp dir so runs never collide
        env["ROCKO_PID"] = os.path.join(self.tmp.name, "rocko.pid")
        env["ROCKO_LOG"] = os.path.join(self.tmp.name, "rocko.log")
        env["TX_PIDFILE"] = os.path.join(self.tmp.name, "beacon.pid")
        env.update(extra)
        return env

    def _run(self, args, env, timeout=20):
        return subprocess.run(
            [SHELL, str(ROCKO), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )

    def test_no_args_reaches_startup_then_fails_nonzero(self):
        # F2 + F13: no args must NOT die at arg parsing; it reaches startup and
        # exits nonzero on the missing (off-Pi) transmitter path.
        proc = self._run([], self._env())
        combined = proc.stdout + proc.stderr
        self.assertIn("Rocko beacon starting", combined)
        self.assertIn("transmitter not found", combined)
        self.assertNotEqual(proc.returncode, 0)

    def test_photo_propagates_classifier_exit_code(self):
        # F13: rocko.sh photo must surface the classifier's real rc, not the
        # numbering pipe's 0.
        stub = os.path.join(self.tmp.name, "stub.py")
        Path(stub).write_text("import sys\nprint('stub ran')\nsys.exit(7)\n")
        proc = self._run(["photo", "x.jpg"], self._env(ROCKO_PHOTO=stub))
        self.assertEqual(proc.returncode, 7)
        self.assertIn("stub ran", proc.stdout + proc.stderr)

    def test_photo_missing_classifier_exits_nonzero(self):
        proc = self._run(
            ["photo"],
            self._env(ROCKO_PHOTO=os.path.join(self.tmp.name, "nope.py")),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("photo classifier not found", proc.stdout + proc.stderr)

    def test_no_cleartext_password_in_script(self):
        # FIX B / review-bot block: the sudo password must never be embedded in
        # the script text. Guard against the old `echo qnxuser | sudo -S ...`.
        src = ROCKO.read_text()
        self.assertNotIn("echo qnxuser", src)
        self.assertNotIn("qnxuser |", src)
        # the bring-up must read the password from a file, not a literal
        self.assertIn("PASS_FILE", src)
        self.assertIn('sudo -S sh -c', src)

    def test_missing_pass_file_degrades_cleanly(self):
        # FIX B: with the mic node absent and NO readable pass-file, rocko.sh
        # must skip the auto bring-up, print the exact manual command, and keep
        # going (it does not abort on the audio path). We stub the transmitter
        # and listener so startup reaches ensure_audio; the transmitter stub
        # exits immediately, so the run then tears down with a nonzero rc.
        tx = os.path.join(self.tmp.name, "tx.py")
        Path(tx).write_text("import sys\nsys.exit(0)\n")
        ls = os.path.join(self.tmp.name, "ls.sh")
        Path(ls).write_text("#!/bin/sh\nexit 0\n")
        env = self._env(
            ROCKO_TRANSMITTER=tx,
            ROCKO_LISTENER=ls,
            MIC_NODE=os.path.join(self.tmp.name, "no_such_mic"),
            ROCKO_PASS_FILE=os.path.join(self.tmp.name, "no_such_pass"),
            ROCKO_AUDIO_WAIT="1",
        )
        proc = self._run([], env)
        combined = proc.stdout + proc.stderr
        # reached the bring-up and degraded cleanly (no crash, no password use)
        self.assertIn("no readable pass-file", combined)
        self.assertIn("sudo sh -c 'slay io-snd", combined)
        # never emitted a cleartext password into the stream
        self.assertNotIn("echo qnxuser", combined)

    def test_orphaned_transmitter_prints_recovery_and_refuses(self):
        # F15: stale rocko.pid + a LIVE transmitter pidfile -> recovery + nonzero.
        live = subprocess.Popen([SHELL, "-c", "sleep 30"])
        self.addCleanup(live.wait)
        self.addCleanup(live.terminate)
        env = self._env()
        Path(env["ROCKO_PID"]).write_text("999999\n")  # stale (dead) owner
        Path(env["TX_PIDFILE"]).write_text(f"{live.pid}\n")  # live orphan
        time.sleep(0.1)
        proc = self._run([], env)
        combined = proc.stdout + proc.stderr
        self.assertIn("still running", combined)
        self.assertIn(f"kill -TERM {live.pid}", combined)
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
