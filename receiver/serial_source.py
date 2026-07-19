#!/usr/bin/env python3
"""Sample sources for the Rocko receiver — serial (real) and CSV replay.

This is the ONLY module that touches the USB serial port, kept deliberately
separate from :mod:`decoder` so the decode pipeline and its unit tests never
need the Pico. Both sources are background threads that push validated
``(t, x, y)`` tuples onto a queue; the GUI/engine drains that queue.

The Pico firmware (``receiver/pico_main.py``) emits ASCII ``t,x,y`` lines at
115200 baud, ~200 Hz. ``ReplaySource`` re-streams a previously recorded CSV at
its original timing so the receiver can be demoed with no hardware attached —
it replays *real* recordings, never synthetic filler.
"""

from __future__ import annotations

import glob
import queue
import threading
import time
from pathlib import Path
from typing import List, Optional

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover - pyserial optional for replay-only use
    serial = None
    list_ports = None


# macOS/Linux USB CDC device patterns for the Pico.
_PORT_GLOBS = ("/dev/cu.usbmodem*", "/dev/tty.usbmodem*", "/dev/ttyACM*")


def autodetect_port() -> Optional[str]:
    """Best-effort single USB-serial port, or None if not exactly one."""
    candidates: List[str] = []
    if list_ports is not None:
        for info in list_ports.comports():
            name = info.device or ""
            if "usbmodem" in name or "ACM" in name or "usbserial" in name:
                candidates.append(name)
    if not candidates:
        for pattern in _PORT_GLOBS:
            candidates.extend(glob.glob(pattern))
    unique = sorted(set(candidates))
    return unique[0] if len(unique) == 1 else None


def list_candidate_ports() -> List[str]:
    ports: List[str] = []
    if list_ports is not None:
        ports.extend(info.device for info in list_ports.comports() if info.device)
    for pattern in _PORT_GLOBS:
        ports.extend(glob.glob(pattern))
    return sorted(set(ports))


def _parse_line(raw: bytes):
    fields = raw.decode("ascii", errors="ignore").strip().split(",")
    if len(fields) != 3:
        return None
    try:
        return float(fields[0]), float(fields[1]), float(fields[2])
    except ValueError:
        return None  # header row or debug print


class SerialSource(threading.Thread):
    """Read ``t,x,y`` lines from the Pico serial port on a background thread."""

    def __init__(self, port: str, baud: int, sink: "queue.Queue", stop_event: threading.Event):
        super().__init__(daemon=True)
        if serial is None:
            raise RuntimeError("pyserial is not installed; run: pip install pyserial")
        self.port = port
        self.sink = sink
        self.stop_event = stop_event
        self.error: Optional[Exception] = None
        self._serial = serial.Serial(port, baud, timeout=0.25)

    def run(self) -> None:
        try:
            while not self.stop_event.is_set():
                raw = self._serial.readline()
                if not raw:
                    continue
                sample = _parse_line(raw)
                if sample is not None:
                    self.sink.put(sample)
        except Exception as exc:  # surfaced by the GUI as an ERROR event
            self.error = exc
            self.stop_event.set()

    def close(self) -> None:
        self.stop_event.set()
        try:
            self._serial.close()
        except Exception:
            pass


class ReplaySource(threading.Thread):
    """Re-stream a recorded ``t,x,y`` CSV at (a multiple of) its real timing."""

    def __init__(
        self,
        csv_path: Path,
        sink: "queue.Queue",
        stop_event: threading.Event,
        speed: float = 1.0,
    ):
        super().__init__(daemon=True)
        self.csv_path = Path(csv_path)
        self.sink = sink
        self.stop_event = stop_event
        self.speed = max(speed, 0.0)
        self.error: Optional[Exception] = None
        self._rows = self._load()

    def _load(self):
        rows = []
        with self.csv_path.open() as handle:
            for line in handle:
                sample = _parse_line(line.encode("ascii", errors="ignore"))
                if sample is not None:
                    rows.append(sample)
        if not rows:
            raise ValueError(f"no t,x,y rows found in {self.csv_path}")
        return rows

    def run(self) -> None:
        try:
            previous_t = self._rows[0][0]
            for sample in self._rows:
                if self.stop_event.is_set():
                    break
                if self.speed > 0:
                    delay = (sample[0] - previous_t) / self.speed
                    if delay > 0:
                        time.sleep(min(delay, 0.5))
                previous_t = sample[0]
                self.sink.put(sample)
        except Exception as exc:
            self.error = exc
            self.stop_event.set()

    def close(self) -> None:
        self.stop_event.set()
