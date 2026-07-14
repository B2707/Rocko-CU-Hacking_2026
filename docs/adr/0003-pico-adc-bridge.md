# Raspberry Pi Pico as the TMR digitizer (ADC bridge)

Decided 2026-07-11. The Raspberry Pi has no analog inputs, and the TMR sensors output analog voltage, so the surface station carries a Pi Pico whose built-in 12-bit ADC samples the sensor and streams values to the laptop over USB serial. Chosen over an ADS1115 I2C breakout because the team already has Picos; side benefit: the Pico's sampling loop gives deterministic sample timing independent of any host scheduling.

Consequences: a small Pico firmware becomes part of the build (sample at a fixed rate ≥ 10× the highest Device Frequency, stream frames over USB-CDC); the TMR output must be conditioned into the Pico's 0–3.3 V / 12-bit window (no on-chip programmable gain, an offset/amplifier stage may be needed, sized after the day-1 bench characterization); and USB-CDC serial support on the laptop's host OS must be smoke-tested day 1, if it fails, fallback is the Pico's UART pins into a GPIO UART, or reverting to an ADS1115 (~$10, rejected alternative).

Verified 2026-07-11: devc-serusb explicitly supports CDC-ACM (official QNX docs + a QNX devblog walkthrough of this exact setup), BUT it is NOT shipped in the Quick Start image, install QNX SDP 8.0 (free myQNX license) and pre-stage the binary (plus devc-serpl011 for the UART fallback; the mini-UART is consumed by the debug console) onto the SD card BEFORE the event.
