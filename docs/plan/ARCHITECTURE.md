# Architecture

One Raspberry Pi 5 total. It goes into the cave, that is where QNX, the AI
models, the microphone, and the coil driver all live. The surface side is
deliberately simple: a sensor, a Pico, and a laptop.

## Explorer device (Raspberry Pi 5, QNX 8, battery powered)

```
[battery pack] --USB-C--> +----------+
[USB mic]      --USB----> |   Pi 5   | GPIO22 --> IN3 -+
[photo input]  --file---> |  QNX 8   | GPIO17 --> IN4  +--> +--------+ OUT3 --> coil
                          +----------+ GPIO27 --> ENB --+   | L298N  |          (~40 ohm)
                                                             |        | OUT4 --> coil
                                                             +--------+
                                              [12 V supply] --> 12V + GND terminals
```

- 12 V touches only the L298N. Grounds are shared between the Pi and the
  driver board.
- Software stack: QNX QSTI image, `apk add python3 python3-numpy
  python3-tflite-runtime` (satisfies the competition's oss.qnx.com AI runtime
  requirement).
- Processes started by `rocko.sh`: the audio listener (whisper.cpp for
  transcription, a compiled C classifier for wake phrase gating and intent
  classification), and the transmitter daemon (encodes frames and drives the
  GPIO pins). `rocko.sh photo` runs the injury image classifier separately.

## Surface station (no second Pi)

```
[coil sensor] --OUT--> ADC pin  +------+
              --GND--> GND      | Pico |--USB-->[laptop]
              --PWR--> 3V3      +------+          receiver/rocko_receiver.py:
                                                    live dashboard + decode + log
```

- The Pico runs `receiver/pico_main.py` (MicroPython), streaming `t,x,y`
  samples at 200 per second over USB serial.
- The laptop installs `receiver/requirements.txt` and runs
  `receiver/rocko_receiver.py`, which auto-detects the serial port.
- Sensor output should stay within 0 to 3.3 V. If the signal is too small,
  add an op amp stage (mid rail bias and gain).

## The frame (12 bits, about 12 seconds on air)

```
[ 0 1 1 1 1 1 1 0 ][ F T L I ]     8 bit tilde preamble
                                    F = fire, T = trapped, L = lost, I = injured
```

- A `1` bit is an 8 Hz tone (the coil polarity flips through the L298N), a
  `0` bit is silence. Manchester encoding is used per bit: a `1` is
  tone-then-silence, a `0` is silence-then-tone. Bit time is 1.0 second.
- Flags are one hot and can combine. `0000` is the heartbeat, sent
  automatically every 120 seconds. `1111` is SOS. See
  [`docs/equipment-codes.md`](../equipment-codes.md) for the full table.
- Emergency frames repeat 3 times with a 3 second gap between repeats, then
  normal heartbeat cadence resumes. This gives the surface decoder three
  independent chances to read the same message correctly.
- The decoder treats energy in the 8 Hz band as a `1`. A correlation against
  the known preamble finds the start of a frame; a majority vote across the
  3 repeats gives the final decoded event.

## Key numbers

- Coil: about 150 turns, 10 to 15 cm radius, roughly 40 ohms, about 0.25 A,
  which gives a field on the order of 75 to 110 nT at 1.5 m.
- Bit time is 1.0 second. Carrier tone is 8 Hz.
- Photo model: EfficientNet-B0 fine-tuned on a wound image dataset, 8 classes,
  converted to TFLite for on device inference. See `photo/README.md`.
- Voice model: whisper.cpp (tiny.en) for transcription, feeding a small
  TF-IDF and logistic regression classifier compiled to native C. Classes are
  fire, injured, lost, trapped, and none. Wake phrase is "hey rocko help".

## Known limits

1. Ambient magnetic noise can sit in the same band as the carrier tone. A
   rigid sensor mount and an adaptive threshold help, but a very noisy
   environment can still produce a missed or garbled frame, which is why
   emergencies repeat 3 times.
2. The live decoder segments messages by watching for a quiet gap. Two
   distinct voice triggers spoken close together (within a few seconds) can
   blend into one capture window. Leaving normal spacing between separate
   emergencies avoids this.
3. There is no camera on this build, so the photo classifier is demonstrated
   against a stored image rather than a live feed.
4. The voice model is trained on a small, clean vocabulary. It works best
   with one designated speaker, a close microphone, and a reasonably quiet
   room.
