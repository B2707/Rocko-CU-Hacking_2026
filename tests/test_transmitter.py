"""Beacon transmitter tests - sim backend only, no hardware or QNX deps."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "transmitter" / "transmitter.py"
SPEC = importlib.util.spec_from_file_location("transmitter", MODULE_PATH)
transmitter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transmitter
assert SPEC.loader is not None
SPEC.loader.exec_module(transmitter)

PRE = "01111110"  # tilde preamble


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += max(0.0, duration)


def make_rig(config=None):
    """Sim backend + fake clock + frame transmitter, wired together."""
    clock = FakeClock()
    config = config or transmitter.Config()
    backend = transmitter.SimBackend(monotonic=clock.monotonic)
    driver = transmitter.CoilDriver(backend, config)
    tx = transmitter.FrameTransmitter(
        driver, config, monotonic=clock.monotonic, sleep=clock.sleep
    )
    return clock, backend, tx


class ManchesterTests(unittest.TestCase):
    def test_regular_manchester_encoding(self):
        self.assertEqual(
            transmitter.regular_manchester("01111110"),
            [0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1],
        )

    def test_rejects_non_binary_message(self):
        for value in ("", "012", "hello"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                transmitter.regular_manchester(value)


class TriggerParsingTests(unittest.TestCase):
    def test_frame_bits_per_class(self):
        cases = {
            "heartbeat": PRE + "0000",
            "fire": PRE + "1000",
            "trapped": PRE + "0100",
            "lost": PRE + "0010",
            "injured": PRE + "0001",
            "sos": PRE + "1111",
            "help": PRE + "1111",
        }
        for name, bits in cases.items():
            batch = transmitter.parse_trigger_text(name)
            with self.subTest(name=name):
                self.assertEqual(batch.unknown, ())
                self.assertTrue(batch.recognized)
                self.assertEqual(transmitter.build_frame(batch.flags), bits)

    def test_flag_combinations_or_together(self):
        batch = transmitter.parse_trigger_text("trapped\ninjured\n")
        self.assertEqual(transmitter.build_frame(batch.flags), PRE + "0101")

    def test_raw_flag_bits_accepted(self):
        batch = transmitter.parse_trigger_text("0101")
        self.assertEqual(batch.unknown, ())
        self.assertEqual(transmitter.build_frame(batch.flags), PRE + "0101")

    def test_none_and_unknown_tokens_never_crash(self):
        batch = transmitter.parse_trigger_text("none")
        self.assertFalse(batch.recognized)
        self.assertEqual(batch.unknown, ())
        batch = transmitter.parse_trigger_text("trapped trapp banana")
        self.assertEqual(batch.flags, transmitter.FLAG_TRAPPED)
        self.assertEqual(batch.unknown, ("trapp", "banana"))
        batch = transmitter.parse_trigger_text("")
        self.assertFalse(batch.recognized)
        self.assertEqual(batch.tokens, 0)

    def test_stop_tokens_case_insensitive(self):
        for token in ("STOP", "Cancel", "CLEAR", "ok"):
            with self.subTest(token=token):
                batch = transmitter.parse_trigger_text(token)
                self.assertTrue(batch.stop)
                self.assertFalse(batch.recognized)
        batch = transmitter.parse_trigger_text("injured STOP")
        self.assertTrue(batch.stop)
        self.assertEqual(batch.flags, transmitter.FLAG_INJURED)

    def test_flags_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            transmitter.build_frame(16)


class SpoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = os.path.join(self.tmp.name, "beacon_trigger")

    def test_consume_is_atomic_and_deletes_both_files(self):
        with open(self.spool, "w", encoding="ascii") as fh:
            fh.write("fire\n")
        batch = transmitter.consume_spool(self.spool)
        self.assertEqual(batch.flags, transmitter.FLAG_FIRE)
        self.assertFalse(os.path.exists(self.spool))
        self.assertFalse(os.path.exists(self.spool + transmitter.SPOOL_WORK_SUFFIX))

    def test_missing_spool_returns_none(self):
        self.assertIsNone(transmitter.consume_spool(self.spool))

    def test_malformed_bytes_never_crash(self):
        with open(self.spool, "wb") as fh:
            fh.write(b"\x00\xff\xfe garbage token\n\n\n")
        batch = transmitter.consume_spool(self.spool)
        self.assertFalse(batch.recognized)
        self.assertFalse(batch.stop)
        self.assertFalse(os.path.exists(self.spool))

    def test_oversized_spool_is_capped_not_fatal(self):
        with open(self.spool, "w", encoding="ascii") as fh:
            fh.write("fire\n" + "z" * (transmitter.SPOOL_MAX_BYTES + 100))
        batch = transmitter.consume_spool(self.spool)
        self.assertEqual(batch.flags, transmitter.FLAG_FIRE)


class TimingTests(unittest.TestCase):
    def test_manchester_half_symbol_timing(self):
        clock, backend, tx = make_rig()
        config = tx.config
        tx.transmit_frame("10")  # halves: tone, off, off, tone

        enb = [(t, v) for t, pin, v in backend.events if pin == config.enb_gpio]
        self.assertEqual(enb[0], (0.0, 1))
        self.assertIn((0.5, 0), enb)
        self.assertIn((1.0, 0), enb)
        self.assertIn((1.5, 1), enb)
        self.assertEqual(enb[-1], (2.0, 0))
        self.assertEqual(clock.now, 2.0)

    def test_tone_is_8hz_polarity_flips(self):
        clock, backend, tx = make_rig()
        config = tx.config
        tx.transmit_frame("1")

        in3 = [
            (t, v)
            for t, pin, v in backend.events
            if pin == config.in3_gpio and t < 0.5
        ]
        self.assertEqual([v for _, v in in3], [1, 0, 1, 0, 1, 0, 1, 0])
        self.assertEqual(
            [round(t, 4) for t, _ in in3], [round(i * 0.0625, 4) for i in range(8)]
        )

    def test_full_frame_takes_twelve_seconds(self):
        clock, _, tx = make_rig()
        tx.transmit_frame(transmitter.build_frame(transmitter.HEARTBEAT_FLAGS))
        self.assertEqual(clock.now, 12.0)

    def test_coil_left_safe_after_frame(self):
        _, backend, tx = make_rig()
        config = tx.config
        tx.transmit_frame(transmitter.build_frame(transmitter.SOS_FLAGS))
        for pin in (config.in3_gpio, config.in4_gpio, config.enb_gpio):
            self.assertEqual(backend.last_value(pin), 0)


class BeaconLoopTests(unittest.TestCase):
    """Daemon behavior: scheduling, queueing, debounce, stop, cleanup."""

    INTERVAL = 30.0
    FRAME = 12.0
    GAP = 3.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = os.path.join(self.tmp.name, "beacon_trigger")

    def spool_writer(self, events):
        """sleep hook: append text to the spool once clock passes each time."""
        remaining = sorted(events)

        def hook(clock):
            while remaining and clock.now >= remaining[0][0]:
                _, text = remaining.pop(0)
                with open(self.spool, "a", encoding="ascii") as fh:
                    fh.write(text)

        return hook

    def make_beacon(self, sleep_hook=None):
        config = transmitter.Config(
            spool_path=self.spool, heartbeat_interval_s=self.INTERVAL
        )
        clock = FakeClock()

        def sleep(duration):
            clock.sleep(duration)
            if sleep_hook:
                sleep_hook(clock)

        backend = transmitter.SimBackend(monotonic=clock.monotonic)
        driver = transmitter.CoilDriver(backend, config)
        tx = transmitter.FrameTransmitter(
            driver, config, monotonic=clock.monotonic, sleep=sleep
        )
        beacon = transmitter.Beacon(tx, config, monotonic=clock.monotonic, sleep=sleep)
        return clock, backend, beacon

    def starts(self, beacon):
        return [t for t, _, _ in beacon.frame_history]

    def kinds(self, beacon):
        return [kind for _, _, kind in beacon.frame_history]

    def test_no_heartbeat_at_startup(self):
        _, backend, beacon = self.make_beacon()
        beacon.run(max_frames=1)
        self.assertEqual(self.kinds(beacon), ["heartbeat"])
        self.assertEqual(self.starts(beacon), [self.INTERVAL])  # not 0.0
        first_event = min(t for t, _, _ in backend.events)
        self.assertGreaterEqual(first_event, self.INTERVAL)  # radio silent before

    def test_stale_spool_discarded_at_startup(self):
        with open(self.spool, "w", encoding="ascii") as fh:
            fh.write("fire\ninjured\n")
        _, _, beacon = self.make_beacon()
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=1)
        self.assertIn("discarded 2 stale trigger(s)", "\n".join(logs.output))
        self.assertEqual(self.kinds(beacon), ["heartbeat"])  # no emergency
        self.assertFalse(os.path.exists(self.spool))

    def test_heartbeat_schedule(self):
        _, _, beacon = self.make_beacon()
        beacon.run(max_frames=3)
        self.assertEqual(self.kinds(beacon), ["heartbeat"] * 3)
        self.assertEqual(self.starts(beacon), [30.0, 60.0, 90.0])

    def test_trigger_mid_frame_waits_then_or_merges(self):
        # two triggers land while the first heartbeat frame (30..42) is on air
        hook = self.spool_writer([(35.0, "trapped\n"), (36.0, "injured\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        beacon.run(max_frames=4)
        self.assertEqual(
            self.kinds(beacon), ["heartbeat", "emergency", "emergency", "emergency"]
        )
        self.assertEqual(self.starts(beacon), [30.0, 42.0, 57.0, 72.0])
        emergency_bits = {b for _, b, k in beacon.frame_history if k == "emergency"}
        self.assertEqual(emergency_bits, {PRE + "0101"})  # OR-merged, one frame
        self.assertFalse(os.path.exists(self.spool))

    def test_duplicate_of_active_class_is_debounced(self):
        # "fire" retriggers while the fire sequence is already on air
        hook = self.spool_writer([(1.0, "fire\n"), (17.0, "fire\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=4)
        self.assertIn("debounced", "\n".join(logs.output))
        # no fourth emergency frame - next frame is a plain heartbeat
        self.assertEqual(
            self.kinds(beacon), ["emergency", "emergency", "emergency", "heartbeat"]
        )
        self.assertEqual(self.starts(beacon), [1.0, 16.0, 31.0, 73.0])

    def test_new_class_queued_during_sequence_transmits_after(self):
        hook = self.spool_writer([(1.0, "fire\n"), (17.0, "lost\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        beacon.run(max_frames=6)
        self.assertEqual(self.kinds(beacon), ["emergency"] * 6)
        bits = [b for _, b, _ in beacon.frame_history]
        self.assertEqual(bits[:3], [PRE + "1000"] * 3)  # fire seq, uninterrupted
        self.assertEqual(bits[3:], [PRE + "0010"] * 3)  # lost seq right after
        self.assertEqual(self.starts(beacon), [1.0, 16.0, 31.0, 43.0, 58.0, 73.0])

    def test_stop_mid_repeats_aborts_and_clears_queue(self):
        # stop (plus a queued class that must ALSO be cleared) lands mid frame 2
        hook = self.spool_writer([(1.0, "fire\n"), (17.0, "lost\nstop\n")])
        _, backend, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=3)
        self.assertIn("stop received", "\n".join(logs.output))
        # frame 2 completed cleanly, repeat 3 aborted, queue cleared,
        # heartbeat timer reset to stop-time + interval (28 + 30)
        self.assertEqual(self.kinds(beacon), ["emergency", "emergency", "heartbeat"])
        self.assertEqual(self.starts(beacon), [1.0, 16.0, 58.0])
        for pin in (beacon.config.in3_gpio, beacon.config.in4_gpio, beacon.config.enb_gpio):
            self.assertEqual(backend.last_value(pin), 0)

    def test_heartbeat_skipped_during_emergency_and_timer_reset(self):
        # sequence 25..67 rolls over the 30 s heartbeat due time
        hook = self.spool_writer([(25.0, "sos\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=4)
        self.assertIn("heartbeat skipped", "\n".join(logs.output))
        self.assertEqual(
            self.kinds(beacon), ["emergency", "emergency", "emergency", "heartbeat"]
        )
        # no heartbeat trails the sequence: timer resets to 67 + 30
        self.assertEqual(self.starts(beacon), [25.0, 40.0, 55.0, 97.0])

    def test_frame_progress_and_signal_sent_logged(self):
        # E6: one full emergency sequence logs per-frame progress, then a single
        # SIGNAL SENT event AFTER the last frame finishes (with its 4-bit code).
        hook = self.spool_writer([(1.0, "injured\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=3)
        out = "\n".join(logs.output)
        self.assertIn("frame 1/3", out)
        self.assertIn("frame 3/3", out)
        self.assertIn("SIGNAL SENT", out)
        self.assertIn("injured (0001)", out)  # E4 code rides with the label
        # SIGNAL SENT must come only after the final frame's completion
        signal_idx = out.index("SIGNAL SENT")
        last_done = out.rindex("tx done: emergency injured (0001) frame 3/3")
        self.assertGreater(signal_idx, last_done)
        self.assertEqual(self.kinds(beacon), ["emergency"] * 3)

    def test_no_signal_sent_when_sequence_aborted(self):
        # a stop mid-sequence aborts the repeats -> NO SIGNAL SENT event
        hook = self.spool_writer([(1.0, "fire\n"), (17.0, "lost\nstop\n")])
        _, _, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertLogs("beacon", level="INFO") as logs:
            beacon.run(max_frames=3)
        out = "\n".join(logs.output)
        self.assertIn("aborted", out)
        self.assertNotIn("SIGNAL SENT", out)

    def test_cleanup_on_interrupt_mid_frame(self):
        def hook(clock):
            if clock.now >= 31.0:  # inside the first heartbeat frame
                raise KeyboardInterrupt

        _, backend, beacon = self.make_beacon(sleep_hook=hook)
        with self.assertRaises(KeyboardInterrupt):
            beacon.run(max_frames=2)
        for pin in (beacon.config.in3_gpio, beacon.config.in4_gpio, beacon.config.enb_gpio):
            self.assertEqual(backend.last_value(pin), 0)

    def test_signal_handler_raises_system_exit(self):
        import signal as signal_module

        with self.assertRaises(SystemExit) as ctx:
            transmitter._raise_exit(signal_module.SIGTERM, None)
        self.assertEqual(ctx.exception.code, 128 + signal_module.SIGTERM)


class LockAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pidfile = os.path.join(self.tmp.name, "beacon.pid")

    def test_second_instance_is_rejected(self):
        first = transmitter.SingleInstanceLock(self.pidfile)
        first.acquire()
        self.addCleanup(first.release)
        second = transmitter.SingleInstanceLock(self.pidfile)
        with self.assertRaises(transmitter.BeaconError):
            second.acquire()

    def test_stale_pidfile_is_taken_over(self):
        # a finished subprocess pid is (almost certainly) not alive any more
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        with open(self.pidfile, "w", encoding="ascii") as pidfile:
            pidfile.write(str(proc.pid))
        lock = transmitter.SingleInstanceLock(self.pidfile)
        lock.acquire()  # must NOT refuse: the process is genuinely dead
        self.addCleanup(lock.release)
        with open(self.pidfile, encoding="ascii") as pidfile:
            self.assertEqual(pidfile.read(), str(os.getpid()))

    def test_invalid_configs_rejected(self):
        with self.assertRaises(ValueError):
            transmitter.Config(in3_gpio=17, in4_gpio=17).validate()
        with self.assertRaises(ValueError):
            transmitter.Config(carrier_hz=3.0).validate()  # 1.5 cycles/half
        with self.assertRaises(ValueError):
            transmitter.Config(bit_seconds=0).validate()

    def test_cli_rejects_unknown_class_and_stop(self):
        log = os.path.join(self.tmp.name, "beacon.log")
        rc = transmitter.main(["--send", "banana", "--sim", "--log-file", log])
        self.assertEqual(rc, 2)
        rc = transmitter.main(["--send", "stop", "--sim", "--log-file", log])
        self.assertEqual(rc, 2)

    def test_spool_deleted_on_exit(self):
        spool = os.path.join(self.tmp.name, "beacon_trigger")
        log = os.path.join(self.tmp.name, "beacon.log")
        with open(spool, "w", encoding="ascii") as fh:
            fh.write("lost\n")
        rc = transmitter.main(
            [
                "--sim",
                "--send",
                "injured",
                "--spool",
                spool,
                "--log-file",
                log,
                "--bit-seconds",
                "0.125",  # fast real-time frame: 12 bits x 0.125 s = 1.5 s
                "--carrier",
                "16",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(spool))  # queue never survives a run


class LabelAndLogFormatTests(unittest.TestCase):
    """E4 coded labels + the --log-plain format rocko.sh relies on."""

    def test_coded_label_carries_the_four_bit_code(self):
        self.assertEqual(
            transmitter.coded_label(transmitter.FLAG_INJURED), "injured (0001)"
        )
        self.assertEqual(transmitter.coded_label(transmitter.SOS_FLAGS), "SOS (1111)")
        self.assertEqual(
            transmitter.coded_label(transmitter.HEARTBEAT_FLAGS), "heartbeat (0000)"
        )
        combo = transmitter.FLAG_TRAPPED | transmitter.FLAG_INJURED
        self.assertEqual(transmitter.coded_label(combo), "trapped+injured (0101)")

    def _run_oneshot(self, extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = os.path.join(tmp.name, "beacon.log")
        rc = transmitter.main(
            ["--sim", "--send", "injured", "--log-file", log,
             "--bit-seconds", "0.125", "--carrier", "16", *extra]
        )
        self.assertEqual(rc, 0)
        return [ln for ln in Path(log).read_text().splitlines() if ln.strip()]

    def test_log_plain_drops_timestamp_and_level(self):
        lines = self._run_oneshot(["--log-plain"])
        self.assertTrue(
            any(ln.startswith("tx start: one-shot injured (0001)") for ln in lines)
        )
        # bare format: no asctime prefix (which would start with a 4-digit year)
        self.assertFalse(any(ln[:4].isdigit() for ln in lines))

    def test_standalone_log_keeps_timestamp(self):
        lines = self._run_oneshot([])
        self.assertTrue(any(ln[:4].isdigit() for ln in lines))  # asctime year


if __name__ == "__main__":
    unittest.main()
