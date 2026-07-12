#!/bin/sh
#
# live_listen.sh (QNX) - live captions + wake-word emergency classifier.
#   USB mic -> waverec (5s chunks) -> whisper.cpp -> classifier (gated on "device")
#
# Every transcript prints like a live caption. If the wake word "device" is
# heard, the phrase after it goes through the emergency classifier and any
# hit prints as an unmissable banner. Ctrl+C to quit.
#
# QNX rewrite of TTS/live_listen.sh (the Linux/WSL original). POSIX sh only
# (/bin/sh is ksh on QNX 8). Paths are absolute so it runs from any cwd.
# Double-buffered: the next chunk records in the background while the
# previous chunk is being transcribed, so almost no speech is missed.

WHISPER=/data/home/qnxuser/whisper.cpp/build/bin/whisper-cli
MODEL=/data/home/qnxuser/whisper.cpp/models/ggml-tiny.en.bin
CLASSIFIER=/data/home/qnxuser/audio/classifier

MIC=plughw:pcmC0D0c        # USB mic
CHUNK=5                    # seconds per recording chunk
WAKE=device                # wake word (keep in sync with wake_word.h)
LISTEN_WINDOW=10           # seconds we stay "armed" after hearing the wake word
BEACON_SPOOL=/tmp/beacon_trigger   # consumed by transmitter/transmitter.py (coil beacon)

WAV_A=/tmp/live_listen_a.$$.wav
WAV_B=/tmp/live_listen_b.$$.wav
rec_pid=""

cleanup() {
    trap - INT TERM
    [ -n "$rec_pid" ] && kill "$rec_pid" 2>/dev/null
    rm -f "$WAV_A" "$WAV_B"
    echo ""
    echo "stopped."
    exit 0
}
trap cleanup INT TERM

for p in "$WHISPER" "$MODEL" "$CLASSIFIER"; do
    if [ ! -e "$p" ]; then
        echo "missing: $p" >&2
        exit 1
    fi
done

echo "Cave Beacon live listen | mic=$MIC | model=tiny.en | chunk=${CHUNK}s"
echo "Say: \"$WAKE <your emergency>\" (e.g. \"$WAKE I am lost\"; adding \"help\" forces an alert). Ctrl+C to quit."
echo "----------------------------------------------------------------"

# Record the first chunk in the background; from then on the loop always has
# one recording in flight while it transcribes the previous one.
waverec -D "$MIC" -r 16000 -c 1 -f S16_LE -t "$CHUNK" "$WAV_A" >/dev/null 2>&1 &
rec_pid=$!
cur=$WAV_A
nxt=$WAV_B
armed_until=0

while :; do
    wait "$rec_pid"
    rec_ok=$?

    # immediately start recording the next chunk (double buffer)
    waverec -D "$MIC" -r 16000 -c 1 -f S16_LE -t "$CHUNK" "$nxt" >/dev/null 2>&1 &
    rec_pid=$!

    if [ "$rec_ok" -ne 0 ]; then
        echo "(mic read failed, retrying)"
        sleep 1
    else
        # transcribe the finished chunk; collapse to one trimmed line
        text=$("$WHISPER" -m "$MODEL" -f "$cur" -nt -np 2>/dev/null \
               | tr '\n' ' ' | tr -s ' ' | sed 's/^ *//; s/ *$//')

        case "$text" in
        ''|'['*']'|'('*')')
            :   # blank or a pure noise annotation like [BLANK_AUDIO] -> skip quietly
            ;;
        *)
            echo "[$(date +%H:%M:%S)] $text"

            lower=$(printf '%s' "$text" | tr 'A-Z' 'a-z')
            now=$(date +%s)
            alert=""
            gated=""
            case " $lower " in
            *[!a-z0-9]"$WAKE"[!a-z0-9]*)
                # wake word in this chunk: the classifier strips everything
                # up to it. Stay armed in case the command spills into the
                # next chunk (same behavior as the Linux script).
                alert=$(printf '%s\n' "$text" | "$CLASSIFIER")
                armed_until=$((now + LISTEN_WINDOW))
                gated=1
                ;;
            *)
                if [ "$now" -lt "$armed_until" ]; then
                    # wake word was heard just before: treat this whole
                    # chunk as the command, then disarm.
                    alert=$(printf '%s %s\n' "$WAKE" "$text" | "$CLASSIFIER")
                    armed_until=0
                    gated=1
                fi
                ;;
            esac

            # Voice off-switch: a wake-gated "stop" / "cancel" / "I am okay"
            # ("device stop") cancels the beacon's emergency queue. Wins over
            # any classifier hit in the same phrase.
            if [ -n "$gated" ]; then
                case " $lower " in
                *[!a-z0-9]stop[!a-z0-9]*|*[!a-z0-9]cancel[!a-z0-9]*|*"i am okay"*|*"i'm okay"*)
                    printf 'stop\n' >> "$BEACON_SPOOL" \
                        || echo "(beacon spool write failed: $BEACON_SPOOL)" >&2
                    echo "--- ================================================== ---"
                    echo "---  CANCELLED  ->  stop sent to beacon (queue cleared)"
                    echo "--- ================================================== ---"
                    alert=""
                    ;;
                esac
            fi

            if [ -n "$alert" ]; then
                echo "!!! ========================================================== !!!"
                echo "!!!  EMERGENCY  ->  $alert"
                echo "!!! ========================================================== !!!"

                # Hand the hit to the coil beacon daemon: the first token of
                # the classifier line is the class; a "[help]" marker forces
                # SOS. "uncertain" / "none" lines never transmit.
                cls=${alert%% *}
                case "$alert" in
                *"[help]"*) cls=sos ;;
                esac
                case "$cls" in
                fire|injured|lost|trapped|sos)
                    printf '%s\n' "$cls" >> "$BEACON_SPOOL" \
                        || echo "(beacon spool write failed: $BEACON_SPOOL)" >&2
                    ;;
                esac
            fi
            ;;
        esac
    fi

    # swap buffers
    t=$cur; cur=$nxt; nxt=$t
done
