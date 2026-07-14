#!/usr/bin/env bash
#
# live_listen.sh - laptop mic demo for the Rocko emergency classifier.
#   mic -> arecord (chunks) -> whisper.cpp -> classifier (wake-phrase gated)
#
# Records short chunks, transcribes each, and feeds the text to the classifier.
# The classifier is the SINGLE wake-phrase gate ("hey rocko help", see
# wake_word.h): a transcript with no wake phrase produces no output. There is no
# cross-chunk arming here, that carry-over (once "device" was heard, later
# chunks were force-classified) was the "no-wake" misfire. Each chunk is one
# independent decision now.
#
# Laptop demo only (the shipped Pi program is rocko.sh). Ctrl+C to stop.

set -uo pipefail

WHISPER="$HOME/whisper.cpp/build/bin/whisper-cli"
MODEL="$HOME/whisper.cpp/models/ggml-base.en.bin"
CLASSIFIER="$HOME/emergency_classifier/classifier"

CHUNK=5                 # seconds per recording chunk
REC_DEV="pulse"         # ALSA device; "pulse" routes through WSLg's mic bridge

tmp="$(mktemp --suffix=.wav)"
trap 'rm -f "$tmp"; echo; echo "stopped."; exit 0' INT

for p in "$WHISPER" "$MODEL" "$CLASSIFIER"; do
    [ -e "$p" ] || { echo "missing: $p"; exit 1; }
done

echo "Listening (${CHUNK}s chunks). Say \"hey rocko help, I'm lost\"."
echo "Say \"hey rocko help\" alone for SOS. Ctrl+C to stop."
echo "----------------------------------------------------------------"

while true; do
    # record one chunk from the mic (through the PulseAudio bridge)
    arecord -D "$REC_DEV" -q -f S16_LE -r 16000 -c 1 -d "$CHUNK" "$tmp" 2>/dev/null || {
        echo "(mic read failed)"; sleep 1; continue
    }

    # transcribe; collapse to a single line
    text="$("$WHISPER" -m "$MODEL" -f "$tmp" --no-timestamps 2>/dev/null \
            | tr '\n' ' ' | sed 's/^ *//; s/ *$//')"
    [ -z "$text" ] && continue

    echo "[heard] $text"
    # The classifier prints a line only when the wake phrase is present.
    printf '%s\n' "$text" | "$CLASSIFIER"
done
