# Operations and Troubleshooting

## Preflight

1. Confirm the Pico serial port.
2. Confirm the Pi IP with one bounded SSH attempt.
3. Confirm no transmitter process or stale PID lock.
4. Force GPIO27, GPIO18, GPIO22, and GPIO17 low.
5. Start `receiver/capture.py` and verify rows are increasing.
6. Confirm its `caffeinate` child is active.
7. Record pre-run silence before starting the transmitter.

## Connectivity rule

If the hotspot/internet path fails, stop and return the issue to the operator.
Do not scan repeatedly, switch networks autonomously, or create indefinite
retry loops. A guest network may isolate wireless clients even when both show
the same SSID.

## Collector architecture

Do not use the Matplotlib live receiver as the authoritative long-duration
collector. Closing the window terminates capture. Use the headless collector
for serial ownership, and use `watch_capture.py` only as a read-only viewer of
the growing CSV.

`caffeinate` prevents idle/display/disk sleep but cannot reliably override
closing a MacBook lid. Keep the laptop powered and open.

## No visible transmitter current

- First run the exact known path: `run-alphabet.sh --start A --once`.
- Do not substitute an ad-hoc GPIO/PWM implementation.
- GPIO27 is the current verified ENB path; GPIO18 PWM is experimental.
- A successful Python return is not physical proof. Check receiver carrier
  response or direct hardware observation.

## False decodes

A restricted alphabet decoder always emits a letter. Reject when the tilde
preamble is weak, the unrestricted header/payload disagrees, margins are low,
clipping occurs, or the H1 likelihood does not exceed calibrated H0.

## Safe stop

Terminate the active transmitter, force all bridge pins low, stop the serial
collector only after a clean post-run gap, copy the manifest/log, and checksum
the immutable raw CSV.
