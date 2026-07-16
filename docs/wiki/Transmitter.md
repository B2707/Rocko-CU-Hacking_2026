# Transmitter

## Canonical commands

Full direct-drive alphabet frame:

```bash
/data/home/qnxuser/run-alphabet.sh --start A --once
```

Finite duty frame through the same GPIO27 driver:

```bash
cd /data/home/qnxuser/transmitter
./duty_pair_test.py --single-duty 10 --letter A
```

Descending dataset:

```bash
./duty_pair_test.py --dataset --manifest RUN.transmitter.csv
```

`--dataset` sends, in order:

- A-E training plus held-out F at 100%.
- A-E training plus held-out G at 50%.
- A-E training plus held-out H at 25%.
- A-E training plus held-out I at 10%.
- A-E training plus held-out J at 1%.

This is 30 frames and takes 35m15s before extra pre/post silence.

## Software-duty limitation

The GPIO27 duty implementation gates ENB inside each 62.5 ms carrier
half-cycle. Representative measured software intervals were:

| Requested | Median software interval |
|---:|---:|
| 10% | 6763 us |
| 1% | 762 us |
| 0.1% | 761 us |

Thus Python/QNX scheduling cannot distinguish requested 1% from 0.1%. A scope
is required for physical pulse-width claims. GPIO18 hardware PWM would require
a separately verified physical wiring path.

## Safe stop

Terminate the active transmitter PID, then force GPIO27, GPIO18, GPIO22, and
GPIO17 low. Never leave cleanup dependent only on normal interpreter exit.
