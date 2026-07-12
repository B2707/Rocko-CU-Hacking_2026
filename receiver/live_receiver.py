#!/usr/bin/env python3
"""Live receiver visualization with automatic end-of-message decoding.

Displays raw ADC channels, a causal bandpass centered on the carrier, and a
smoothed carrier-amplitude detector. After observing a tone, five continuous
seconds without tone triggers the Hilbert/template decoder.
"""

import argparse
from collections import deque
from datetime import datetime
from pathlib import Path
import queue
import subprocess
import sys
import threading

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
from scipy import signal
import serial


class SerialReader(threading.Thread):
    def __init__(self, port, baud, samples, stop_event):
        super().__init__(daemon=True)
        self.samples = samples
        self.stop_event = stop_event
        self.serial = serial.Serial(port, baud, timeout=0.25)
        self.error = None

    def run(self):
        try:
            while not self.stop_event.is_set():
                raw = self.serial.readline()
                if not raw:
                    continue
                fields = raw.decode("ascii", errors="ignore").strip().split(",")
                if len(fields) != 3:
                    continue
                try:
                    self.samples.put(tuple(map(float, fields)))
                except ValueError:
                    continue
        except Exception as exc:
            self.error = exc
            self.stop_event.set()

    def close(self):
        self.stop_event.set()
        self.serial.close()


class LiveReceiver:
    def __init__(self, args):
        self.args = args
        self.sample_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.reader = SerialReader(args.port, args.baud, self.sample_queue, self.stop_event)

        output = args.output or (
            Path("captures") / f"live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self.output = Path(output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.csv = self.output.open("w", buffering=1)
        self.csv.write("t,x,y\n")

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
        self.last_tone_time = None
        self.decode_pending = False
        self.last_result = "Waiting for tone"

        self.fig, self.axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        self.raw_x, = self.axes[0].plot([], [], lw=0.8, label="X")
        self.raw_y, = self.axes[0].plot([], [], lw=0.8, label="Y", alpha=0.8)
        self.band_x, = self.axes[1].plot([], [], lw=0.8, label="X bandpass")
        self.band_y, = self.axes[1].plot([], [], lw=0.8, label="Y bandpass", alpha=0.8)
        self.env_line, = self.axes[2].plot([], [], lw=1, label="carrier amplitude")
        self.threshold_line, = self.axes[2].plot([], [], "r--", lw=1, label="tone threshold")
        self.status = self.axes[2].text(
            0.01, 0.97, self.last_result, transform=self.axes[2].transAxes,
            va="top", bbox={"facecolor": "white", "alpha": 0.8}
        )
        self.axes[0].set_ylabel("Raw ADC")
        self.axes[1].set_ylabel("Filtered ADC")
        self.axes[1].set_title(f"{low:g}-{high:g} Hz bandpass")
        self.axes[2].set_ylabel("Amplitude")
        self.axes[2].set_xlabel("Receiver time (s)")
        for axis in self.axes:
            axis.grid(alpha=0.25)
            axis.legend(loc="upper right")
        self.fig.suptitle(f"Live receiver: {args.port}")
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect("close_event", lambda _: self.close())
        self.animation = None

    def _drain_samples(self):
        rows = []
        while True:
            try:
                rows.append(self.sample_queue.get_nowait())
            except queue.Empty:
                break
        if not rows:
            return

        values = np.asarray(rows)
        times, raw_x, raw_y = values.T
        for timestamp, xv, yv in rows:
            self.csv.write(f"{timestamp:.6f},{xv:g},{yv:g}\n")

        if self.zi_x is None:
            # Start each bandpass in the steady state for the ADC's initial DC
            # level, avoiding a false tone caused by filter startup transient.
            self.zi_x = signal.sosfilt_zi(self.sos) * raw_x[0]
            self.zi_y = signal.sosfilt_zi(self.sos) * raw_y[0]
        filtered_x, self.zi_x = signal.sosfilt(self.sos, raw_x, zi=self.zi_x)
        filtered_y, self.zi_y = signal.sosfilt(self.sos, raw_y, zi=self.zi_y)
        instantaneous = np.sqrt(filtered_x**2 + filtered_y**2)
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
                    self.seen_tone = True
                if self.seen_tone:
                    self.last_tone_time = timestamp
            else:
                self.tone_run = 0.0

        if self.seen_tone and self.last_tone_time is not None:
            silence = times[-1] - self.last_tone_time
            self.last_result = f"Tone detected; silence {max(0, silence):.1f}/{self.args.silence}s"
            if silence >= self.args.silence and not self.decode_pending:
                self.decode_pending = True
                self.csv.flush()
                self._decode()

    def _decode(self):
        scores = self.output.with_name(self.output.stem + "_scores.csv")
        decoder = Path(__file__).with_name("decode_tilde_message.py")
        command = [
            sys.executable, str(decoder), str(self.output),
            "--carrier", str(self.args.carrier),
            "--bandwidth", str(self.args.bandwidth),
            "--message-bits", str(self.args.message_bits),
            "-o", str(scores),
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode == 0:
            binary_line = next(
                (line for line in result.stdout.splitlines() if line.startswith("Binary message:")),
                "Binary message: unknown",
            )
            self.last_result = binary_line
            print(result.stdout, flush=True)
        else:
            self.last_result = "Decode failed; see terminal"
            print(result.stderr or result.stdout, file=sys.stderr, flush=True)
        self.seen_tone = False
        self.last_tone_time = None
        self.decode_pending = False
        if self.args.stop_after_decode:
            self.close()
            plt.close(self.fig)

    @staticmethod
    def _set_limits(axis, x_values, y_values):
        if len(x_values) < 2:
            return
        axis.set_xlim(x_values[0], x_values[-1])
        low, high = np.percentile(y_values, [1, 99])
        margin = max((high - low) * 0.1, 1.0)
        axis.set_ylim(low - margin, high + margin)

    def update_plot(self, _frame):
        self._drain_samples()
        if self.reader.error:
            self.last_result = f"Serial error: {self.reader.error}"
        if len(self.t) < 2:
            self.status.set_text(self.last_result)
            return ()

        t = np.asarray(self.t)
        x, y = np.asarray(self.x), np.asarray(self.y)
        fx, fy = np.asarray(self.fx), np.asarray(self.fy)
        envelope = np.asarray(self.envelope)
        self.raw_x.set_data(t, x)
        self.raw_y.set_data(t, y)
        self.band_x.set_data(t, fx)
        self.band_y.set_data(t, fy)
        self.env_line.set_data(t, envelope)
        self.threshold_line.set_data(t, np.full_like(t, self.threshold))
        self._set_limits(self.axes[0], t, np.concatenate((x, y)))
        self._set_limits(self.axes[1], t, np.concatenate((fx, fy)))
        self._set_limits(self.axes[2], t, np.r_[envelope, self.threshold])
        self.status.set_text(self.last_result)
        return self.raw_x, self.raw_y, self.band_x, self.band_y, self.env_line, self.threshold_line

    def run(self):
        print(f"Recording {self.args.port} -> {self.output}")
        print(f"Auto-decode after {self.args.silence:g} seconds without an 8 Hz tone")
        self.reader.start()
        self.animation = FuncAnimation(
            self.fig, self.update_plot, interval=100, blit=False, cache_frame_data=False
        )
        plt.show()

    def close(self):
        if not self.stop_event.is_set():
            self.reader.close()
        if not self.csv.closed:
            self.csv.flush()
            self.csv.close()
        print(f"Saved {self.output}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--port", required=True)
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("-o", "--output")
    parser.add_argument("--sample-rate", type=float, default=200.0)
    parser.add_argument("--carrier", type=float, default=8.0)
    parser.add_argument("--bandwidth", type=float, default=2.0)
    parser.add_argument("--message-bits", type=int, default=16)
    parser.add_argument("--silence", type=float, default=5.0)
    parser.add_argument("--tone-confirm", type=float, default=0.5)
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
