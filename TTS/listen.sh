#!/usr/bin/env bash
#
# listen.sh - transcribe an audio file and classify it.
#   audio file -> ffmpeg (16kHz mono) -> whisper.cpp -> emergency classifier
#
# Usage:
#   ./listen.sh recording.wav
#   ./listen.sh clip.m4a          (any format ffmpeg can read)
#
# Edit the three paths below if yours differ.

set -euo pipefail

WHISPER="$HOME/whisper.cpp/build/bin/whisper-cli"
MODEL="$HOME/whisper.cpp/models/ggml-base.en.bin"
CLASSIFIER="$HOME/emergency_classifier/classifier"

if [ $# -lt 1 ]; then
    echo "usage: $0 <audio-file>"
    exit 1
fi
infile="$1"

for p in "$WHISPER" "$MODEL" "$CLASSIFIER"; do
    if [ ! -e "$p" ]; then echo "missing: $p"; exit 1; fi
done

# whisper.cpp wants 16 kHz mono WAV; resample whatever we were given.
tmp="$(mktemp --suffix=.wav)"
trap 'rm -f "$tmp"' EXIT
ffmpeg -y -i "$infile" -ar 16000 -ac 1 "$tmp" >/dev/null 2>&1

# transcribe (no timestamps) and pipe the text into the classifier
"$WHISPER" -m "$MODEL" -f "$tmp" --no-timestamps 2>/dev/null | "$CLASSIFIER"
