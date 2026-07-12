#!/usr/bin/env bash
#
# live_listen.sh - continuous mic listening for the emergency classifier.
#   mic -> arecord (chunks) -> whisper.cpp -> emergency classifier
#
# Records short chunks, transcribes each, and feeds the text to the classifier.
# Handles the wake word ACROSS chunks: once "device" is heard, a listening
# window opens for a few seconds so the command can arrive in a later chunk.
#
# Laptop demo only. Ctrl+C to stop.

set -uo pipefail

WHISPER="$HOME/whisper.cpp/build/bin/whisper-cli"
MODEL="$HOME/whisper.cpp/models/ggml-base.en.bin"
CLASSIFIER="$HOME/emergency_classifier/classifier"

CHUNK=3                 # seconds per recording chunk
WAKE="device"           # wake word (keep in sync with wake_word.h)
LISTEN_WINDOW=8         # seconds to keep listening after hearing the wake word
REC_DEV="pulse"         # ALSA device; "pulse" routes through WSLg's mic bridge

tmp="$(mktemp --suffix=.wav)"
trap 'rm -f "$tmp"; echo; echo "stopped."; exit 0' INT

for p in "$WHISPER" "$MODEL" "$CLASSIFIER"; do
    [ -e "$p" ] || { echo "missing: $p"; exit 1; }
done

echo "Listening (${CHUNK}s chunks). Say \"${WAKE}, I'm lost\". Ctrl+C to stop."
echo "----------------------------------------------------------------"

armed_until=0           # epoch seconds until which we're in the listen window

while true; do
    # record one chunk from the mic (through the PulseAudio bridge)
    arecord -D "$REC_DEV" -q -f S16_LE -r 16000 -c 1 -d "$CHUNK" "$tmp" 2>/dev/null || {
        echo "(mic read failed)"; sleep 1; continue
    }

    # transcribe; collapse to a single lowercase line
    text="$("$WHISPER" -m "$MODEL" -f "$tmp" --no-timestamps 2>/dev/null \
            | tr '\n' ' ' | sed 's/^ *//; s/ *$//')"
    [ -z "$text" ] && continue

    now=$(date +%s)
    lower="$(printf '%s' "$text" | tr '[:upper:]' '[:lower:]')"

    if printf '%s' "$lower" | grep -qw "$WAKE"; then
        # wake word present in this chunk: classify normally (classifier strips
        # everything up to the wake word) AND open the listening window in case
        # the command continues into the next chunk.
        echo "[heard] $text"
        printf '%s\n' "$text" | "$CLASSIFIER"
        armed_until=$(( now + LISTEN_WINDOW ))
    elif [ "$now" -lt "$armed_until" ]; then
        # still inside the listen window from a previous "device": treat this
        # whole chunk as the command, then close the window so trailing speech
        # isn't swept up too.
        echo "[heard, still listening] $text"
        printf '%s %s\n' "$WAKE" "$text" | "$CLASSIFIER"
        armed_until=0
    else
        # idle: no wake word, not listening -> ignore
        echo "[ignored] $text"
    fi
done
