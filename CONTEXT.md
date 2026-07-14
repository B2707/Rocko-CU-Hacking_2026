# Rocko, glossary

Rocko is a cave explorer safety beacon. One device goes into the cave with
the explorer, a receiver station stays at the surface. The explorer's device
talks through rock using a magnetic field: a regular heartbeat, plus a
voice-triggered emergency message classified on device. If the pings stop
arriving (device damaged, battery dead, collapse), the surface station
raises the alarm on its own. Silence is the alarm.

## Words we use

**Explorer device**
The unit that goes into the cave: a Raspberry Pi 5 on QNX with a microphone
and the coil driver.

**Surface station**
The unit that stays outside: a magnetic sensor, a Pico, a laptop, and the
live dashboard.

**Frame**
What travels through the rock: an 8 bit tilde preamble, then 4 flag bits.
12 bits total, about 12 seconds on air.

**Heartbeat**
A frame with all flags clear, sent automatically every 120 seconds. The
surface station shows the device as alive as long as heartbeats keep
arriving. Too long without one raises the alarm.

**Flags**
The 4 bit field: fire, trapped, lost, injured. One hot per emergency, and
they can combine (a real world event can be more than one thing at once).
The frozen table lives in `docs/equipment-codes.md`, this is the contract
between the voice classifier on the explorer device and the decoder on the
surface station.

**Wake phrase**
"Hey Rocko, help", the spoken trigger. Saying it alone sends an SOS. Saying
it followed by a description of what happened lets the specific emergency
class win.

**Coil link**
The path: GPIO pins, L298N driver board, coil, through rock, sensor, Pico,
laptop. One way, slow on purpose, and that is fine for this use case.

**Tone**
The 8 Hz beep the coil makes for the "on" half of a Manchester encoded bit.
