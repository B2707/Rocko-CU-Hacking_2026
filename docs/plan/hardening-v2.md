# Hardening v2, Cave Explorer Safety Beacon (2026-07-12)

Source of truth for this build round. Written from Bader's instructions verbatim,
plus three decisions he confirmed today. Agents: read fully before touching code.

## Confirmed decisions (Bader, 2026-07-12)

1. **Wake phrase = "hey rocko help".** Saying the phrase ALONE (nothing after)
   sends SOS (1111). If words follow ("hey rocko help I'm trapped"), the
   specific classified class wins instead of SOS.
2. **Auto audio bring-up approved.** The one-program launcher may detect a
   missing mic (/dev/snd/pcmC0D0c absent) and itself run
   `echo qnxuser | sudo -S sh -c "slay io-snd; io-snd -c /etc/system/config/sound/io_snd.conf"`.
   This is the ONLY sanctioned automatic restart, and only inside the shipped
   launcher when Bader runs it, agents must NEVER run it themselves.
3. **Injury-image model** (UPDATED after Bader's pointer): the real classifier
   lives in `B2707/hackathon-team-template` PR #33 (merged), folder `CNN/`,    EfficientNet-B0 **PyTorch** (`CNN/outputs/best_model.pt`), 8 wound classes,
   88.5% test acc, with `predict.py`/`config.py`/`model.py` and demo-ready
   `test_data/` photos. PyTorch does NOT run on QNX; a separate conversion
   task produces `injury.tflite` + `labels.txt` for the Pi's tflite-runtime.
   The Pi photo script stays a generic drop-in: model path + labels file
   next to it; degrade gracefully with a clear "model not installed yet"
   message when absent. Demo photo comes from `CNN/test_data/`.
4. **Frame/bit contract is UNCHANGED.** Bader (verbatim): "make sure you are
   not changing the origianl way the signal bits and shit were set as we
   agreed on". The frozen table below IS the agreed contract, do not alter
   preamble, bit assignments, modulation, timing, repeat counts, or heartbeat
   period in any way. This round only ADDS logging, naming, and robustness
   around it.
5. **Only the classifiers that exist today.** Audio classes stay exactly
   {fire, injured, lost, trapped, none} + the [help] keyword override, no new
   classes, no retraining. The photo model is whatever train_cnn.py produced
   (teammate drop-in); read its class labels from a labels file shipped next
   to the model, don't hardcode.
6. **The project is named Rocko.** The one-program launcher is `rocko.sh`,
   terminal banners and logs say Rocko, docs use the name.

## Explorer side (QNX Pi), branch `task/raspberry-pi-transmitter` (PR #9)

- **E1 Wake phrase**: replace "device" with "hey rocko help". Match robustly
  against whisper transcription variants (case, punctuation, "rocco"/"rocko"/
  "rockö"/"roko", comma splits). Strip the wake phrase from the transcript
  before classification. Phrase alone → SOS per decision 1.
- **E2 No-wake bug (Bader observed it live)**: during signal testing, input was
  accepted WITHOUT the wake phrase. Find the gate bypass (suspects: `--raw`
  test flag leaking into the live path, "help" keyword override firing before
  the wake gate, cross-chunk arming never disarming) and fix. Test: transcript
  with emergency content but no wake phrase → NO spool write, NO transmission.
- **E3 Misfire hardening**: wake gate must be the single choke point; add
  confidence threshold on classification; no re-trigger from the device's own
  banner text; cooldown so one utterance can't double-fire across chunk overlap.
- **E4 Official codes**: the table in `docs/equipment-codes.md` (below) is
  frozen as the official contract. Every log line that mentions an emergency
  must include its 4-bit code, e.g. `injured (0001)`, `SOS (1111)`,
  `trapped+injured (0101)`. Commit this spec to `docs/plan/hardening-v2.md`
  and make sure `docs/equipment-codes.md` on the branch matches the table below.
- **E5 One program**: single entry point on the Pi named `rocko.sh` replacing
  the pile of test scripts. On start: (a) audio auto-bring-up per decision 2,
  (b) start transmitter daemon, (c) start live listener, (d) unified terminal
  output where EVERY event line carries a monotonically increasing event number
  `[#0001]` and a timestamp. One Ctrl+C stops everything, coil forced off.
- **E6 Event lifecycle logging** (Bader: "add more details like signal sending
  and then once a signal is fully sent it should print signal sent"):
  numbered events for: heard/transcribed text, classification + code, queued,
  transmission start (frame n/3), **`SIGNAL SENT` printed only after the final
  frame fully finishes, with the completion timestamp** (Bader's idea: log tx
  time after the event signal is fully done transmitting, to reduce errors).
  Same stream mirrored to a log file on the Pi.
- **E7 Photo injury classification demo** (no camera): `bench/`-style script
  (deployed to Pi) that loads the teammate's `.tflite` via tflite-runtime
  (oss.qnx.com package, competition requirement), classifies a demo photo,
  prints class + confidence as a numbered event. Document the drop-in paths
  (model + photo). Integrate as a launcher subcommand (e.g. `rocko.sh photo`).
- **E8 Edge cases / error hardening** (Bader: "think of all possible edge cases
  and error senarios and account for all of them"): mic vanishes mid-run
  (detect + numbered ERROR + instruct relaunch; the sanctioned sudo audio
  bring-up runs ONLY at rocko.sh startup per decision 2, never mid-run while
  the coil may be transmitting), whisper crash or empty transcript, classifier binary missing, spool write failure, GPIO node
  missing, transmitter already running, disk-full on logs, double launch,
  clean shutdown on every signal path (coil OFF guaranteed), log file growth
  capped or rotated. Never crash the loop; every failure = numbered ERROR event.

## Receiver side (Mohammad's laptop, wired to MDT sensor → Pico → USB)

Base: PR #10 `task/receiver-visualization` (capture + matplotlib viz + decoder).
Work on a NEW branch `task/receiver-v2` from PR #10's head (don't force-push
Mohammad's branch).

- **R1**: keep Mohammad's capture/matplotlib stack; polish, don't rewrite.
- **R2 Charts**: top = sensor 1 raw signal; middle = bandpass-filtered signal
  (around the 8 Hz tone); bottom = same content as the current bottom pane.
- **R3**: larger/clearer decode point markers.
- **R4 Decoder**: rework to the official contract below, tilde preamble
  01111110 + 4 flag bits, Manchester (1→tone/no-tone, 0→no-tone/tone), 8 Hz
  tone, 1.0 s/bit, emergency frames repeat 3×/3 s gaps, heartbeat 0000 every
  120 s. Include unit tests decoding a synthetic generated waveform.
- **R5 Logging**: every recorded signal and decoded event/emergency type logged
  with timestamps + event numbers, to file and a compact on-screen list.
- **R6 GUI feel**: easy to read, nice looking, simple, NOT overcrowded. Do NOT
  pre-populate with fake data, panes start empty until real signals arrive.
- **R7**: one program, one command to launch (runs locally on the laptop).
- **R8 Serial contract gap (found during mapping)**: PR #10's receiver expects
  ASCII `t,x,y` lines (2 ADC channels) at ~200 Hz over USB serial, but the only
  Pico firmware in the repo (`bench/pico_main.py`) emits bare single-channel
  integers. Close the gap: update the Pico firmware to emit the `t,x,y` format
  the receiver expects (keep it MicroPython-simple), commit it alongside the
  receiver, and document the wiring/channel mapping in the receiver README.

## Official frame contract (frozen, matches docs/equipment-codes.md)

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

## Review standard, MISSION-CRITICAL, CANNOT-FAIL (Bader, verbatim intent)

"This is supposed to be a mission critical device, adding more stuff to break
only gives us more headache. Go by mission-critical cannot-fail standards."
Verify/review agents MUST apply this:

- **Complexity is a defect.** Any feature, abstraction, config knob, or code
  path not required by this spec is a finding (high severity if it sits in the
  transmit path or the wake gate). Recommend REMOVAL, not polish.
- **Fail-safe over feature-rich.** Every failure must degrade toward the safe
  state: coil OFF, heartbeat cadence preserved, silence-is-alarm never
  compromised. A crash that stops heartbeats is worse than a missing feature.
- **Single choke points, no parallel paths.** One wake gate, one spool writer
  discipline, one launcher. Duplicate/alternate paths to transmit = critical.
- **Deterministic over clever.** No heuristics where a simple rule works; no
  dependencies beyond what already ships; no background threads/processes
  beyond the ones the spec names.
- **Judge additions like they will run 300 m underground with no operator.**
  If a reviewer can't say what happens when a component fails, that IS the
  finding.

## Safety rules, EVERY agent, no exceptions

- Pi ssh is READ-ONLY plus: scp file copies, `make` in /data/home/qnxuser/audio,
  `python3 -m py_compile`, `apk add` (idempotent installs). That's it.
- NEVER slay/restart/shutdown ANYTHING on the Pi (incl. io-snd, decision 2
  authorizes only the shipped launcher, run by Bader, to do that).
- NEVER write to /dev/gpio/*, Bader's hands may be in the wiring.
- NEVER run transmitter.py, live_listen.sh, beacon.sh, or any long-running
  binary on the Pi. No `find /` on the Pi. Don't pipe long-running Pi commands
  through head/grep.
- PR #9 stays UNMERGED until the coil is verified live (Bader's standing rule).
  Same restraint for the receiver branch: push + PR, no merges.
- Pi may be offline (hotspot). Handle gracefully, report, move on.

## Repo/process

- Small commits, conventional messages. Python-only changes need the
  `test-exempt` label on PRs, otherwise touch tests too (they should anyway).
- CI: build-test, hooks-test, tests-touched, review (bot may flake no-verdict
  once, re-run before treating as real).
- Pi shell scripts must be POSIX sh (QNX ships ksh, no bash). No bashisms;
  syntax-check with `sh -n`.
- Local repo quirk: primary checkout sits on `main` with uncommitted local
  edits; worktree agents must fetch and check out their branch explicitly, and
  push with `git push origin HEAD:<branch>` if a plain checkout is blocked.
