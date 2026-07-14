# Real-time scope + bit reader for the coil link. Plots WHILE you transmit.
#   pip install pyserial numpy matplotlib
#   python3 live_scope.py /dev/tty.usbmodem*    (mac)
#   python3 live_scope.py COM5                  (windows)
#   python3 live_scope.py /dev/ttyACM0          (linux, default)
# Top panel: raw signal scrolling live. Bottom: tone energy vs threshold.
# Title: the bits it reads, updating as they arrive.
import sys
import collections
import threading
import serial
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
RATE = 200            # must match pico_main.py
WINDOW_S = 15         # seconds of history on screen
BIT_SECONDS = 1.0     # must match send_bits.py
NUM_BITS = 8          # how many bits per burst (e.g. 10101110)
THRESHOLD = 0.05      # tone-energy cutoff - tune while watching the bottom panel

buf = collections.deque(maxlen=RATE * WINDOW_S)

def reader():
    ser = serial.Serial(PORT, 115200, timeout=1)
    while True:
        line = ser.readline().strip()
        if line.isdigit():
            buf.append(int(line) / 65535.0 - 0.5)   # center around 0

threading.Thread(target=reader, daemon=True).start()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
raw_line, = ax1.plot([], [], lw=0.8)
env_line, = ax2.plot([], [], lw=1.2, color="tab:orange")
ax2.axhline(THRESHOLD, ls="--", color="tab:red")
ax1.set_ylabel("signal")
ax2.set_ylabel("tone energy")
ax2.set_xlabel("seconds")
ax1.set_ylim(-0.55, 0.55)
ax2.set_ylim(0, 0.4)
title = fig.suptitle("waiting for signal...")

ENV_WIN = int(RATE * 0.25)   # energy averaged over quarter-second chunks

def update(_):
    data = np.array(buf)
    if len(data) < ENV_WIN:
        return raw_line, env_line
    t = np.arange(len(data)) / RATE
    raw_line.set_data(t, data)
    # rolling RMS = "is the tone on right now?"
    rms = np.sqrt(np.convolve(data ** 2, np.ones(ENV_WIN) / ENV_WIN, mode="same"))
    env_line.set_data(t, rms)
    ax1.set_xlim(0, len(data) / RATE)
    # live bit read: first energy = start; then sample mid-bit every BIT_SECONDS
    on = rms > THRESHOLD
    if on.any():
        start = int(np.argmax(on))
        step = int(RATE * BIT_SECONDS)
        centers = start + step // 2 + np.arange(NUM_BITS) * step
        centers = centers[centers < len(rms)]
        bits = "".join("1" if rms[c] > THRESHOLD else "0" for c in centers)
        title.set_text(f"decoded: {bits}")
    return raw_line, env_line

ani = animation.FuncAnimation(fig, update, interval=80)
plt.show()
