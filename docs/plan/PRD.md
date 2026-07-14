# PRD, Cave Explorer Safety Beacon

## Problem
Cave explorers lose all radio contact underground. When something goes wrong, injury, getting lost, getting stuck, a collapse, nobody on the surface knows,
and nobody knows what help to bring.

## Product
A handheld beacon the explorer carries plus a surface receiver. The beacon talks
through solid rock using a low-frequency magnetic field (proven tech: real mine
rescue systems have done this for decades).

## Core features
1. **Alive ping**, every few minutes the beacon automatically sends a short
   fixed signal. The surface shows "OK, last heard X min ago".
2. **Silence alarm (the cannot-fail feature)**, if pings stop for too long
   (collapse, crushed device, dead battery), the surface goes red BY ITSELF.
   The failure case needs no working hardware underground.
3. **Voice emergencies**, "Hey <device>, I'm stuck" → wake-word + keyword AI
   picks the emergency type: lost / injured / stuck / health problem.
4. **Camera injury check**, on "injured", the camera photographs the injury and
   a CNN classifies it (burn / cut / bruise / laceration…), so the surface knows
   what rescue equipment to bring.
5. **Live surface display**, real-time signal plot, decoded message, and a big
   green / yellow / red status.

## Hard constraints (competition)
- Runs on QNX on the Raspberry Pi 5 (embedded, no cloud).
- Uses an open-source AI module from oss.qnx.com → satisfied by
  `python3-tflite-runtime` running both our models.
- Judges score: cannot-fail? real-time/reliable? creative AI? on-hardware?

## Explicit non-goals (keep it shallow)
- One explorer device, one surface box. No fleets.
- 16 message types max (4 bits) + 16 details (4 bits). No text, no images over
  the link (physically impossible at ~1 bit/s anyway).
- No error-correcting codes, the message repeats forever instead.
- No enclosure engineering, a box that survives a demo, not a cave.

## Demo = success criteria
1. Beacon pings, surface shows green with "last heard" ticking.
2. Speak an emergency → within ~30 s the surface shows the type + equipment.
3. Kill the beacon's power → surface goes red on its own. (The money shot.)
