# Hardening v2 — Cave Explorer Safety Beacon (2026-07-12)

Source of truth for this build round. Written from Bader's instructions verbatim,
plus decisions he confirmed on 2026-07-12. Agents: read fully before touching code.

## Confirmed decisions (Bader, 2026-07-12)

1. **Wake phrase = "hey rocko help".** Saying the phrase ALONE (nothing after)
   sends SOS (1111). If words follow ("hey rocko help I'm trapped"), the
   specific classified class wins instead of SOS.
2. **Auto audio bring-up approved.** The one-program launcher may detect a
   missing mic (/dev/snd/pcmC0D0c absent) and itself run
   `echo qnxuser | sudo -S sh -c "slay io-snd; io-snd -c /etc/system/config/sound/io_snd.conf"`.
   This is the ONLY sanctioned automatic restart, and only inside the shipped
   launcher when Bader runs it — agents must NEVER run it themselves.
3. **Injury-image model**: EfficientNet-B0 (PyTorch) trained by the team, 8 wound
   classes. PyTorch does NOT run on QNX; a separate conversion task produces
   `injury.tflite` + `labels.txt` for the Pi's tflite-runtime. The Pi photo script
   stays a generic drop-in: model path + labels file next to it; degrade gracefully
   with a clear "model not installed yet" message when absent.
4. **Frame/bit contract is UNCHANGED.** The frozen table in
   `docs/equipment-codes.md` IS the agreed contract — do not alter preamble, bit
   assignments, modulation, timing, repeat counts, or heartbeat period in any way.
   This round only ADDS logging, naming, and robustness around it.
5. **Only the classifiers that exist today.** Audio classes stay exactly
   {fire, injured, lost, trapped, none} + the [help] keyword override — no new
   classes, no retraining. The photo model reads its class labels from a labels
   file shipped next to the model, never hardcoded.
6. **The project is named Rocko.** The one-program launcher is `rocko.sh`,
   terminal banners and logs say Rocko, docs use the name.

## Explorer side (QNX Pi) — branch `task/raspberry-pi-transmitter` (PR #9)

- **E1 Wake phrase**: replace "device" with "hey rocko help". Match robustly
  against whisper transcription variants (case, punctuation, "rocco"/"rocko"/
  "rockö"/"roko", comma splits). Strip the wake phrase from the transcript
  before classification. Phrase alone → SOS per decision 1.
- **E2 No-wake bug**: during signal testing, input was accepted WITHOUT the wake
  phrase. Root cause: the shell listener's cross-chunk "arming window" prepended
  a fake wake word to any utterance heard within 10 s of a wake mention, so
  emergency content with no wake phrase could transmit. Fix: the C classifier's
  wake gate is the single choke point; the shell pipes raw transcripts and never
  fabricates a wake word. Test: transcript with emergency content but no wake
  phrase → NO spool write, NO transmission.
- **E3 Misfire hardening**: wake gate is the single choke point; confidence
  threshold on classification (already present); no re-trigger from the device's
  own banner text (banners are terminal-only, never fed back to the classifier);
  cooldown so one utterance can't double-fire across chunk overlap.
- **E4 Official codes**: the table in `docs/equipment-codes.md` is frozen as the
  official contract. Every log line that mentions an emergency includes its 4-bit
  code, e.g. `injured (0001)`, `SOS (1111)`, `trapped+injured (0101)`.
- **E5 One program**: single entry point on the Pi named `rocko.sh` replacing the
  pile of test scripts. On start: (a) audio auto-bring-up per decision 2, (b) start
  transmitter daemon, (c) start live listener, (d) unified terminal output where
  EVERY event line carries a monotonically increasing event number `[#0001]` and a
  timestamp. One Ctrl+C stops everything, coil forced off.
- **E6 Event lifecycle logging**: numbered events for heard/transcribed text,
  classification + code, queued, transmission start (frame n/3), **`SIGNAL SENT`
  printed only after the final frame fully finishes, with the completion
  timestamp**. Same stream mirrored to a log file on the Pi.
- **E7 Photo injury classification demo** (no camera): script (deployed to Pi)
  that loads the teammate's `.tflite` via tflite-runtime (oss.qnx.com package —
  competition requirement), classifies a demo photo, prints class + confidence as
  a numbered event. Documents the drop-in paths (model + photo). Integrated as a
  launcher subcommand: `rocko.sh photo`.
- **E8 Edge cases / error hardening**: mic vanishes mid-run (re-detect, clear
  error; auto-fix once at launch), whisper crash or empty transcript, classifier
  binary missing, spool write failure, GPIO node missing, transmitter already
  running, disk-full on logs, double launch, clean shutdown on every signal path
  (coil OFF guaranteed), log file growth capped or rotated. Never crash the loop;
  every failure = numbered ERROR event.

## Official frame contract (frozen — matches docs/equipment-codes.md)

| Bits | Field | Value |
|------|----------|-------|
| 8 | Preamble | `01111110` (tilde) |
| 4 | Flags | `bit3=fire  bit2=trapped  bit1=lost  bit0=injured` |

| Flags | Meaning |
|-------|---------|
| 0000 | Heartbeat (auto every 120 s; silence is the alarm) |
| 1000 | Fire |
| 0100 | Trapped |
| 0010 | Lost |
| 0001 | Injured |
| 1111 | SOS / help |
| other | Combination (flags OR) e.g. 0101 = trapped+injured |

Physical: 8 Hz square tone via IN3/IN4 flips (62.5 ms half-cycles), ENB gates
on/off, coil OUT3/OUT4, Manchester, 1.0 s/bit, GPIO22→IN3 GPIO17→IN4 GPIO27→ENB.
Classifier class `none` never transmits.

## Safety rules — EVERY agent, no exceptions

- Pi ssh is READ-ONLY plus: scp file copies, `make` in /data/home/qnxuser/audio,
  `python3 -m py_compile`, `apk add` (idempotent installs). That's it.
- NEVER slay/restart/shutdown ANYTHING on the Pi (incl. io-snd — decision 2
  authorizes only the shipped launcher, run by Bader, to do that).
- NEVER write to /dev/gpio/* — Bader's hands may be in the wiring.
- NEVER run transmitter.py, live_listen.sh, rocko.sh, or any long-running binary
  on the Pi. Deployment happens later, separately.
- PR #9 stays UNMERGED until the coil is verified live (Bader's standing rule).
- Pi may be offline (hotspot). Handle gracefully, report, move on.

## Repo/process

- Small commits, conventional messages. Python-only changes need the
  `test-exempt` label on PRs, otherwise touch tests too.
- Pi shell scripts must be POSIX sh (QNX ships ksh, no bash). No bashisms;
  syntax-check with `sh -n`.
</content>
