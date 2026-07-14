# Cave Beacon coil transmitter (QNX 8 / Raspberry Pi 5)

Long-running beacon daemon that drives the L298N coil through the QNX
`rpi_gpio` resource manager (`/dev/gpio`). No pigpio, no Linux libraries.

- **Tone** = 8 Hz square wave made by flipping coil polarity on IN3/IN4
  (62.5 ms per half-cycle) with ENB high. **No tone** = ENB low.
- **Encoding**: regular Manchester per bit (`1 -> tone/no-tone`,
  `0 -> no-tone/tone`), bit time 1.0 s (0.5 s half-symbols = 4 carrier
  cycles per tone half).
- **Frame (12 bits, ~12 s)**: tilde preamble `01111110`, then 4 flag bits
  MSB-first, `bit3=fire  bit2=trapped  bit1=lost  bit0=injured`.
  `0000` = heartbeat, `1111` = SOS ("help" keyword override), combinations
  legal (`0101` = trapped+injured). Full table: `docs/equipment-codes.md`.
- **Behavior**: silent at launch, the daemon transmits NOTHING at startup;
  the first heartbeat fires one full period (120 s) after start, then every
  120 s. Emergencies may transmit any time: triggers arrive via the spool
  file `/tmp/beacon_trigger` (class names or 4-bit flag strings, written by
  `TTS/live_listen_qnx.sh`). A frame mid-transmission is always finished
  first (~12 s worst wait), then the pending flags go out 3x with 3 s gaps
  and the heartbeat timer resets. A stale spool or pidfile from a previous
  run is cleared at startup, the trigger queue never survives across runs.

### Queueing: merge-then-queue, not FIFO

Triggers that arrive while a frame or sequence is on air are never lost and
never interleaved: they accumulate into a pending set whose flags OR-merge
(injured then lost -> one `0011` frame), and transmit as the NEXT sequence
after the current one completes. A class already on air or already pending
is debounced (logged, not re-queued). This beats a naive FIFO because the
receiver learns **both** dangers in one 12 s frame instead of waiting ~45 s
for two back-to-back sequences, on a channel this slow, latency to the full
picture is what saves the explorer. A heartbeat that comes due during an
emergency sequence is skipped (the emergency itself proves aliveness), and
after any emergency sequence the heartbeat timer resets to now + 120 s.

### Stop command (voice off-switch)

Spool tokens `stop` / `cancel` / `clear` / `ok` (case-insensitive) finish
the current frame cleanly, abort the remaining repeats, clear the pending
queue, and resume the heartbeat schedule (timer reset). Saying
"hey rocko help stop" (or "... cancel" / "... I am okay") into the mic does
exactly this via `live_listen_qnx.sh`, the cancel word is wake-gated, so a
stray "stop" in conversation never clears a real emergency.

## Wiring (BCM numbering)

| Raspberry Pi | L298N |
|---|---|
| GPIO22 | IN3 |
| GPIO17 | IN4 |
| GPIO27 | ENB |
| GND | GND (shared with Pi) |

Coil on **OUT3/OUT4**. Remove the ENB jumper (GPIO27 controls ENB).
12 V pack only on the L298N motor supply, never on the Pi.

## Deploy (QNX Pi, `ssh qnxpi`)

```sh
scp transmitter/transmitter.py qnxpi:/data/home/qnxuser/transmitter/
ssh qnxpi 'python3 -m py_compile /data/home/qnxuser/transmitter/transmitter.py'
```

Python 3 comes from oss.qnx.com (`apk add python3`). The daemon needs the
`rpi_gpio` resource manager running (`pidin | grep -i gpio`).

**GPIO interface (verified on qnxpi 2026-07-12):** `rpi_gpio` mounts one text
node per pin under `/dev/gpio`; commands are written with no trailing newline
(`echo -n out|on|off > /dev/gpio/<pin>`). That is exactly what
`QnxGpioBackend` does. The nodes are `rw-rw---- uid gpio`, if writes are
denied, run as a user in the `gpio` group (or sudo).

## Run

```sh
# bench one-shot (single frame, then exit) - start here
python3 transmitter.py --send heartbeat
python3 transmitter.py --send injured
python3 transmitter.py --send trapped --send injured   # 0101 combo

# the real thing: daemon (silent start; first heartbeat at +120 s)
python3 transmitter.py

# poke the running daemon
echo injured >> /tmp/beacon_trigger
echo stop >> /tmp/beacon_trigger      # cancel: finish frame, clear queue

# no-hardware dry run (works on the Mac too)
python3 transmitter.py --sim --send sos
```

Every frame is logged with timestamp+bits to `/tmp/beacon.log` (small,
rotating). A pidfile (`/tmp/beacon.pid`) guarantees a single instance, two processes can never fight over the coil. On SIGINT/SIGTERM/crash the
coil is driven off and ENB pulled low, always.

All timing/pins/paths are constants in `Config` (no magic numbers);
`--heartbeat-interval`, `--bit-seconds`, `--carrier`, `--spool`,
`--pidfile`, `--log-file`, `--gpio-dev` override per run.

## Tests

```sh
python3 -m pytest tests/test_transmitter.py -q   # sim backend, no hardware
```

## Safety / first live test

1. Motor supply OFF, run `--send heartbeat`, scope the IN3/IN4/ENB pins.
2. Motor supply ON, `--send heartbeat` again, watch the surface scope
   (`bench/live_scope.py`) for the 12 s frame.
3. Only then start the daemon.

The L298N heats up at high current, cool it, current-limit the supply,
and use a coil rated for the voltage and duty cycle.
