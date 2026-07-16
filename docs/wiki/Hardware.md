# Hardware

## Transmitter

- Raspberry Pi 5 running QNX 8.0.0.
- L298N bridge driving the transmitter coil.
- Verified direct-drive wiring:
  - BCM GPIO22 -> IN3
  - BCM GPIO17 -> IN4
  - BCM GPIO27 -> ENB
- The canonical direct-drive path is `/data/home/qnxuser/run-alphabet.sh`.

GPIO18 hardware PWM was explored, but it is not the currently verified physical
path. Do not substitute it for GPIO27 without rewiring and a physical test.

The 8 Hz carrier is produced by reversing IN3/IN4 every 62.5 ms. Manchester OOK
enables or disables ENB for each one-second half-symbol.

## Receiver

- Raspberry Pi Pico receiver connected by USB CDC.
- Two 12-bit sensor values streamed as `t,x,y` at approximately 200 Hz.
- Common macOS port: `/dev/cu.usbmodem1201`; enumeration can change.

## Safety invariant

After success, interruption, failure, or operator stop, configure ENB, IN3, and
IN4 as outputs and force them low. Current operational cleanup also forces
GPIO18 low defensively.

Do not infer physical transmission from a successful Python return code. Verify
the canonical hardware path and receiver carrier response.
