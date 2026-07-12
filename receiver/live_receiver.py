#!/usr/bin/env python3
"""Rocko live receiver dashboard.

Three stacked panes plus a compact event panel:

    top     sensor 1 raw ADC
    middle  sensor 1 bandpass around the 8 Hz carrier
    bottom  combined carrier amplitude + adaptive tone threshold
    right   Rocko status header + recent numbered events

Samples arrive from a serial port (or a CSV replay) via :mod:`serial_source`.
A causal tone detector arms on a confirmed carrier and, after enough continuous
silence (long enough to span the 3 s inter-repeat gaps but not the 120 s
heartbeat), decodes the recent window in-process with :mod:`decoder` and marks
the decode point on the amplitude pane.

The panes start EMPTY — nothing is drawn until real samples arrive.
"""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
from pathlib import Path
import queue
import threading

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np
from scipy import signal

import decoder
from eventlog import EventLog
from protocol import (
    BANDWIDTH_HZ,
    CARRIER_HZ,
    DEFAULT_SAMPLE_RATE_HZ,
    HEARTBEAT_PERIOD_SECONDS,
    REPEAT_GAP_SECONDS,
)
from serial_source import ReplaySource, SerialSource

# Visual identity — muted, readable, works on a projector.
COLOR_RAW = "#2563eb"
COLOR_BAND = "#0891b2"
COLOR_AMP = "#059669"
COLOR_THRESH = "#dc2626"
COLOR_MARK = "#f59e0b"
COLOR_PANEL_BG = "#0f172a"
COLOR_PANEL_FG = "#e2e8f0"


class LiveReceiver:
    def __init__(self, args, event_log: EventLog | None = None):
        self.args = args
        self.sample_queue: "queue.Queue" = queue.Queue()
        self.stop_event = threading.Event()

        if getattr(args, "replay", None):
            self.source = ReplaySource(
                Path(args.replay), self.sample_queue, self.stop_event,
                speed=getattr(args, "speed", 1.0),
            )
            source_label = f"replay {Path(args.replay).name}"
        else:
            self.source = SerialSource(
                args.port, args.baud, self.sample_queue, self.stop_event
            )
            source_label = args.port
        self.source_label = source_label

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = args.output or (Path("captures") / f"live_{stamp}.csv")
        self.output = Path(output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.csv = self.output.open("w", buffering=1)
        self.csv.write("t,x,y\n")

        self.log = event_log or EventLog(Path("captures") / f"rocko_{stamp}.log")

        self.max_plot_samples = round(args.plot_seconds * args.sample_rate)
        self.t = deque(maxlen=self.max_plot_samples)
        self.x = deque(maxlen=self.max_plot_samples)
        self.y = deque(maxlen=self.max_plot_samples)
        self.fx = deque(maxlen=self.max_plot_samples)
        self.fy = deque(maxlen=self.max_plot_samples)
        self.envelope = deque(maxlen=self.max_plot_samples)
        self.detector_history = deque(maxlen=round(60 * args.sample_rate))

        low = args.carrier - args.bandwidth / 2
        high = args.carrier + args.bandwidth / 2
        self.band_label = f"{low:g}-{high:g} Hz bandpass"
        self.sos = signal.butter(
            4, [low, high], btype="bandpass", fs=args.sample_rate, output="sos"
        )
        self.zi_x = None
        self.zi_y = None
        self.envelope_state = 0.0
        self.envelope_alpha = 1 - np.exp(-1 / (args.sample_rate * 0.25))

        self.threshold = 0.0
        self.separation = 0.0
        self.tone_run = 0.0
        self.seen_tone = False
        self.signal_logged = False
        self.last_tone_time = None
        self.decode_pending = False
        self.status_line = "Waiting for the first signal…"
        self._marker_artists: list = []

        self._build_figure()
        self.animation = None

    # --- figure ------------------------------------------------------------

    def _build_figure(self):
        self.fig = plt.figure(figsize=(15, 9))
        try:
            self.fig.canvas.manager.set_window_title("Rocko — cave beacon receiver")
        except Exception:  # headless / Agg backend has no window manager
            pass
        grid = GridSpec(
            3, 2, width_ratios=[3.1, 1.15], height_ratios=[1, 1, 1.15],
            hspace=0.28, wspace=0.04, left=0.06, right=0.985, top=0.9, bottom=0.08,
        )
        self.ax_raw = self.fig.add_subplot(grid[0, 0])
        self.ax_band = self.fig.add_subplot(grid[1, 0], sharex=self.ax_raw)
        self.ax_amp = self.fig.add_subplot(grid[2, 0], sharex=self.ax_raw)
        self.ax_side = self.fig.add_subplot(grid[:, 1])
        self.ax_side.axis("off")

        (self.raw_line,) = self.ax_raw.plot([], [], lw=0.9, color=COLOR_RAW)
        (self.band_line,) = self.ax_band.plot([], [], lw=0.9, color=COLOR_BAND)
        (self.env_line,) = self.ax_amp.plot(
            [], [], lw=1.3, color=COLOR_AMP, label="carrier amplitude"
        )
        (self.threshold_line,) = self.ax_amp.plot(
            [], [], "--", lw=1.2, color=COLOR_THRESH, label="tone threshold"
        )

        self.ax_raw.set_ylabel("Sensor 1 raw ADC")
        self.ax_raw.set_title("Sensor 1 — raw", loc="left", fontsize=10, color="#334155")
        self.ax_band.set_ylabel("Sensor 1 bandpass")
        self.ax_band.set_title(
            f"Sensor 1 — {self.band_label}", loc="left", fontsize=10, color="#334155"
        )
        self.ax_amp.set_ylabel("Carrier amplitude")
        self.ax_amp.set_xlabel("Receiver time (s)")
        self.ax_amp.set_title(
            "Carrier amplitude + adaptive tone threshold",
            loc="left", fontsize=10, color="#334155",
        )
        self.ax_amp.legend(loc="upper right", fontsize=8, framealpha=0.85)
        for axis in (self.ax_raw, self.ax_band, self.ax_amp):
            axis.grid(alpha=0.22)
            axis.margins(x=0)

        self.fig.suptitle(
            "ROCKO  ·  cave explorer safety beacon — surface receiver",
            fontsize=15, fontweight="bold", x=0.06, ha="left",
        )
        self.side_text = self.ax_side.text(
            0.0, 1.0, "", transform=self.ax_side.transAxes, va="top", ha="left",
            family="monospace", fontsize=9, color=COLOR_PANEL_FG,
            bbox={"boxstyle": "round,pad=0.6", "facecolor": COLOR_PANEL_BG,
                  "edgecolor": "#334155"},
        )
        self.fig.canvas.mpl_connect("close_event", lambda _evt: self.close())

    # --- sample intake -----------------------------------------------------

    def _drain_samples(self):
        rows = []
        while True:
            try:
                rows.append(self.sample_queue.get_nowait())
            except queue.Empty:
                break
        if not rows:
            return

        values = np.asarray(rows, dtype=float)
        times, raw_x, raw_y = values.T
        for timestamp, xv, yv in rows:
            self.csv.write(f"{timestamp:.6f},{xv:g},{yv:g}\n")

        if self.zi_x is None:
            # Seed each bandpass at the ADC's initial DC level so the filter
            # startup transient does not masquerade as a tone.
            self.zi_x = signal.sosfilt_zi(self.sos) * raw_x[0]
            self.zi_y = signal.sosfilt_zi(self.sos) * raw_y[0]
        filtered_x, self.zi_x = signal.sosfilt(self.sos, raw_x, zi=self.zi_x)
        filtered_y, self.zi_y = signal.sosfilt(self.sos, raw_y, zi=self.zi_y)
        instantaneous = np.sqrt(filtered_x ** 2 + filtered_y ** 2)
        smoothed = np.empty_like(instantaneous)
        for index, amplitude in enumerate(instantaneous):
            self.envelope_state += self.envelope_alpha * (amplitude - self.envelope_state)
            smoothed[index] = self.envelope_state

        self.t.extend(times)
        self.x.extend(raw_x)
        self.y.extend(raw_y)
        self.fx.extend(filtered_x)
        self.fy.extend(filtered_y)
        self.envelope.extend(smoothed)
        self.detector_history.extend(smoothed)
        self._update_detector(times, smoothed)

    # --- tone / end-of-message detector -----------------------------------

    def _update_detector(self, times, amplitudes):
        history = np.asarray(self.detector_history)
        if len(history) < self.args.sample_rate:
            return
        floor, high = np.percentile(history, [10, 90])
        self.separation = high - floor
        self.threshold = floor + 0.30 * self.separation
        detector_ready = high > max(floor * 3.0, floor + self.args.min_separation)

        for timestamp, amplitude in zip(times, amplitudes):
            tone = detector_ready and amplitude > self.threshold
            if tone:
                self.tone_run += 1 / self.args.sample_rate
                if self.tone_run >= self.args.tone_confirm:
                    if not self.seen_tone and not self.signal_logged:
                        self.log.emit("SIGNAL", "carrier detected — recording beacon")
                        self.signal_logged = True
                    self.seen_tone = True
                if self.seen_tone:
                    self.last_tone_time = timestamp
            else:
                self.tone_run = 0.0

        if self.seen_tone and self.last_tone_time is not None:
            silence = times[-1] - self.last_tone_time
            self.status_line = (
                f"Tone captured — silence {max(0.0, silence):.1f}/{self.args.silence:g}s"
            )
            if silence >= self.args.silence and not self.decode_pending:
                self.decode_pending = True
                self.csv.flush()
                self._decode()

    def _decode(self):
        try:
            result = decoder.decode_repeats(
                np.asarray(self.t), np.asarray(self.x), np.asarray(self.y),
                carrier=self.args.carrier, bandwidth=self.args.bandwidth,
            )
        except Exception as exc:  # never let a bad capture kill the loop
            self.log.emit("ERROR", f"decode failed: {exc}")
            self.status_line = f"Decode failed: {exc}"
            self._reset_after_decode()
            return

        self.log.emit(
            "DECODE",
            f"{result.label} ({result.code}) — {result.agreement}",
        )
        self.status_line = f"Decoded: {result.label} ({result.code})"
        self._add_decode_markers(result)
        self._reset_after_decode()
        if self.args.stop_after_decode:
            self.close()
            plt.close(self.fig)

    def _reset_after_decode(self):
        self.seen_tone = False
        self.signal_logged = False
        self.last_tone_time = None
        self.decode_pending = False

    def _add_decode_markers(self, result):
        """Big, clear markers at each decoded frame start on the amplitude pane."""
        top = max(self.envelope) if self.envelope else 1.0
        for index, frame in enumerate(result.frames):
            line = self.ax_amp.axvline(
                frame.start_time, color=COLOR_MARK, lw=1.4, alpha=0.8, zorder=4
            )
            star = self.ax_amp.scatter(
                [frame.start_time], [top], marker="*", s=320,
                color=COLOR_MARK, edgecolor="#7c2d12", linewidth=0.8, zorder=6,
            )
            label = self.ax_amp.annotate(
                f"{result.code}\n{result.label}" if index == 0 else result.code,
                xy=(frame.start_time, top), xytext=(4, -6),
                textcoords="offset points", fontsize=8, fontweight="bold",
                color="#7c2d12", zorder=6,
            )
            self._marker_artists.append((frame.start_time, [line, star, label]))

    def _prune_markers(self, left_edge):
        keep = []
        for start_time, artists in self._marker_artists:
            if start_time < left_edge:
                for artist in artists:
                    artist.remove()
            else:
                keep.append((start_time, artists))
        self._marker_artists = keep

    # --- rendering ---------------------------------------------------------

    @staticmethod
    def _set_limits(axis, x_values, y_values):
        if len(x_values) < 2:
            return
        axis.set_xlim(x_values[0], x_values[-1])
        low, high = np.percentile(y_values, [1, 99])
        margin = max((high - low) * 0.12, 1.0)
        axis.set_ylim(low - margin, high + margin)

    _PANEL_WIDTH = 34  # characters; keeps text inside the narrow side panel

    @classmethod
    def _clip(cls, text: str) -> str:
        return text if len(text) <= cls._PANEL_WIDTH else text[: cls._PANEL_WIDTH - 1] + "…"

    def _render_side_panel(self):
        log_name = self.log.path.name if self.log.path else "-"
        header = [
            "ROCKO RECEIVER",
            "-" * self._PANEL_WIDTH,
            f"source : {self.source_label}",
            f"rate   : {self.args.sample_rate:g} Hz",
            f"samples: {len(self.t)}",
            f"log    : {log_name}",
            "",
            self.status_line,
            "",
            "RECENT EVENTS",
            "-" * self._PANEL_WIDTH,
        ]
        events = self.log.recent()
        if events:
            body = [event.compact() for event in events]
        else:
            body = ["(none yet — panes stay empty", " until a real signal arrives)"]
        lines = ["  " + self._clip(line) for line in header + body]
        self.side_text.set_text("\n".join(lines))

    def update_plot(self, _frame):
        self._drain_samples()
        source_error = getattr(self.source, "error", None)
        if source_error is not None:
            message = f"source error: {source_error}"
            if self.status_line != message:
                self.log.emit("ERROR", message)
            self.status_line = message

        if len(self.t) >= 2:
            t = np.asarray(self.t)
            self.raw_line.set_data(t, np.asarray(self.x))
            self.band_line.set_data(t, np.asarray(self.fx))
            self.env_line.set_data(t, np.asarray(self.envelope))
            self.threshold_line.set_data(t, np.full_like(t, self.threshold))
            self._set_limits(self.ax_raw, t, np.asarray(self.x))
            self._set_limits(self.ax_band, t, np.asarray(self.fx))
            self._set_limits(
                self.ax_amp, t, np.r_[np.asarray(self.envelope), self.threshold]
            )
            self._prune_markers(t[0])

        self._render_side_panel()
        return ()

    # --- lifecycle ---------------------------------------------------------

    def run(self):
        self.log.emit(
            "CAPTURE",
            f"listening on {self.source_label} -> {self.output}",
        )
        self.log.emit(
            "READY",
            f"auto-decode after {self.args.silence:g}s silence "
            f"(spans {REPEAT_GAP_SECONDS:g}s repeat gaps, "
            f"under {HEARTBEAT_PERIOD_SECONDS:g}s heartbeat)",
        )
        self.source.start()
        from matplotlib.animation import FuncAnimation

        self.animation = FuncAnimation(
            self.fig, self.update_plot, interval=100, blit=False,
            cache_frame_data=False,
        )
        plt.show()

    def close(self):
        if not self.stop_event.is_set():
            self.source.close()
        if not self.csv.closed:
            self.csv.flush()
            self.csv.close()
        self.log.emit("CAPTURE", f"stopped — saved {self.output}", echo=True)
        self.log.close()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-p", "--port", help="serial port, e.g. /dev/cu.usbmodem1201")
    source.add_argument("--replay", help="re-stream a recorded t,x,y CSV (no hardware)")
    parser.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier")
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("-o", "--output")
    parser.add_argument("--sample-rate", type=float, default=DEFAULT_SAMPLE_RATE_HZ)
    parser.add_argument("--carrier", type=float, default=CARRIER_HZ)
    parser.add_argument("--bandwidth", type=float, default=BANDWIDTH_HZ)
    parser.add_argument("--silence", type=float, default=5.0)
    parser.add_argument("--tone-confirm", type=float, default=0.3)
    parser.add_argument("--min-separation", type=float, default=2.0)
    parser.add_argument("--plot-seconds", type=float, default=90.0)
    parser.add_argument("--stop-after-decode", action="store_true")
    return parser.parse_args()


def main():
    app = LiveReceiver(parse_args())
    try:
        app.run()
    finally:
        app.close()


if __name__ == "__main__":
    main()
