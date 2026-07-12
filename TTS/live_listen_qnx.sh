#!/bin/sh
#
# live_listen_qnx.sh (QNX) - live captions + wake-phrase emergency classifier.
#   USB mic -> waverec (5 s chunks) -> whisper.cpp -> classifier (single gate)
#
# Every transcript prints like a live caption. The classifier is THE gate: a
# chunk is piped in raw and only reacts if it contains the wake phrase
# "hey rocko help". Phrase-alone -> SOS; wake-gated stop/cancel -> cancel;
# otherwise the classified emergency class is queued to the beacon spool.
#
# There is deliberately NO shell-side wake matching and NO cross-chunk arming
# window: the old arming window prepended a fake wake word to any utterance for
# 10 s after a wake mention, which let emergency content with no wake phrase
# transmit (the E2 no-wake bug). The single choke point now lives in the C
# classifier's after_wake_word(); this script never fabricates a wake word.
#
# POSIX sh only (/bin/sh is ksh on QNX 8). Absolute paths so it runs from any
# cwd. Double-buffered: the next chunk records in the background while the
# previous chunk is transcribed, so almost no speech is missed.
#
# Normally launched by rocko.sh, which numbers + timestamps every line and
# mirrors them to a log. Standalone it prints its own [HH:MM:SS] caption stamp.
# Set ROCKO_NUMBERED=1 to suppress the local stamp (rocko owns numbering).

WHISPER=/data/home/qnxuser/whisper.cpp/build/bin/whisper-cli
MODEL=/data/home/qnxuser/whisper.cpp/models/ggml-tiny.en.bin
CLASSIFIER=/data/home/qnxuser/audio/classifier

MIC=plughw:pcmC0D0c              # USB mic (ALSA-style name for waverec)
MIC_NODE=/dev/snd/pcmC0D0c       # capture device node (existence = mic present)
CHUNK=5                          # seconds per recording chunk
WAKE_PHRASE="hey rocko help"     # spoken wake phrase (matched in wake_word.h)
COOLDOWN=8                       # seconds to suppress repeat fires (chunk overlap)
# F10: honor a BEACON_SPOOL override from the environment so rocko.sh's --spool
# path reaches BOTH the listener (writer) and the transmitter (reader).
BEACON_SPOOL="${BEACON_SPOOL:-/tmp/beacon_trigger}"

WAV_A=/tmp/live_listen_a.$$.wav
WAV_B=/tmp/live_listen_b.$$.wav
WHISPER_OUT=/tmp/live_listen_out.$$.txt
rec_pid=""

# --- event output -------------------------------------------------------
# One clean line per event so rocko.sh's numberer can prefix [#NNNN] + time.
emit() {
    printf '%s\n' "$*"
}
caption() {
    if [ -n "${ROCKO_NUMBERED:-}" ]; then
        printf 'heard: %s\n' "$1"
    else
        printf '[%s] heard: %s\n' "$(date +%H:%M:%S)" "$1"
    fi
}

# 4-bit code for a single emergency class (E4: every emergency line shows it).
code_for() {
    case "$1" in
        fire)    echo 1000 ;;
        trapped) echo 0100 ;;
        lost)    echo 0010 ;;
        injured) echo 0001 ;;
        sos)     echo 1111 ;;
        *)       echo "----" ;;
    esac
}

spool_write() {
    # Append one token to the beacon spool; ERROR event on failure (E8).
    if printf '%s\n' "$1" >> "$BEACON_SPOOL" 2>/dev/null; then
        return 0
    fi
    emit "ERROR beacon spool write failed ($BEACON_SPOOL) - trigger '$1' dropped"
    return 1
}

cleanup() {
    trap - INT TERM
    [ -n "$rec_pid" ] && kill "$rec_pid" 2>/dev/null
    rm -f "$WAV_A" "$WAV_B" "$WHISPER_OUT"
    emit "listener stopped."
    exit 0
}
trap cleanup INT TERM

for p in "$WHISPER" "$MODEL" "$CLASSIFIER"; do
    if [ ! -e "$p" ]; then
        emit "ERROR missing required file: $p"
        exit 1
    fi
done

emit "Rocko live listen | mic=$MIC | model=tiny.en | chunk=${CHUNK}s"
emit "Say: \"$WAKE_PHRASE <emergency>\" (e.g. \"$WAKE_PHRASE I am lost\")."
emit "Say \"$WAKE_PHRASE\" alone for SOS; \"$WAKE_PHRASE stop\" to cancel. Ctrl+C to quit."

# First chunk records in the background; from then on the loop always has one
# recording in flight while it transcribes the previous one.
waverec -D "$MIC" -r 16000 -c 1 -f S16_LE -t "$CHUNK" "$WAV_A" >/dev/null 2>&1 &
rec_pid=$!
cur=$WAV_A
nxt=$WAV_B
cooldown_until=0
mic_warned=0        # mic node vanished (suppress repeat ERRORs)
read_warned=0       # mic present but read failing (suppress repeat ERRORs, F14)
whisper_warned=0    # whisper pipeline failing (suppress repeat ERRORs, F8)

while :; do
    wait "$rec_pid"
    rec_ok=$?

    # immediately start recording the next chunk (double buffer)
    waverec -D "$MIC" -r 16000 -c 1 -f S16_LE -t "$CHUNK" "$nxt" >/dev/null 2>&1 &
    rec_pid=$!

    if [ "$rec_ok" -ne 0 ]; then
        # E8: mic read failed. Distinguish a vanished device from a transient
        # glitch. Never crash the loop; the sanctioned io-snd auto-fix lives in
        # rocko.sh (decision 2) - the listener only reports and keeps retrying.
        if [ ! -e "$MIC_NODE" ]; then
            if [ "$mic_warned" -eq 0 ]; then
                emit "ERROR mic vanished: $MIC_NODE absent - re-run rocko.sh to auto-fix audio"
                mic_warned=1
            fi
        else
            # F14: device present but the read failed - suppress repeats so a
            # persistent glitch cannot spam one ERROR per second; report once.
            if [ "$read_warned" -eq 0 ]; then
                emit "ERROR mic read failed (device present) - retrying, further repeats suppressed"
                read_warned=1
            fi
        fi
        sleep 2
        t=$cur; cur=$nxt; nxt=$t
        continue
    fi
    [ "$mic_warned" -eq 1 ] && { emit "mic recovered: $MIC_NODE present"; mic_warned=0; }
    [ "$read_warned" -eq 1 ] && { emit "mic read recovered"; read_warned=0; }

    # Transcribe the finished chunk to a file so we can read whisper's OWN exit
    # status (a pipeline into tr/sed would mask it). F8: a whisper crash must
    # surface as a numbered ERROR - a deaf device - distinct from the silence of
    # an empty transcript, which is normal.
    "$WHISPER" -m "$MODEL" -f "$cur" -nt -np >"$WHISPER_OUT" 2>/dev/null
    wrc=$?
    if [ "$wrc" -ne 0 ]; then
        if [ "$whisper_warned" -eq 0 ]; then
            emit "ERROR whisper transcription failed (exit $wrc) - device deaf this chunk, retrying; repeats suppressed"
            whisper_warned=1
        fi
        t=$cur; cur=$nxt; nxt=$t
        continue
    fi
    [ "$whisper_warned" -eq 1 ] && { emit "whisper recovered"; whisper_warned=0; }
    text=$(tr '\n' ' ' < "$WHISPER_OUT" | tr -s ' ' | sed 's/^ *//; s/ *$//')

    case "$text" in
    ''|'['*']'|'('*')')
        : ;;   # E8: blank / pure noise annotation -> skip quietly (whisper was OK)
    *)
        caption "$text"

        # SINGLE GATE: pipe the raw transcript straight to the classifier. It
        # prints nothing unless the wake phrase is present, so no wake = no
        # spool write = no transmission (E2). fail-closed on classifier error.
        if ! line=$(printf '%s\n' "$text" | "$CLASSIFIER" 2>/dev/null); then
            emit "ERROR classifier failed - fail-closed, no transmit this chunk"
            t=$cur; cur=$nxt; nxt=$t
            continue
        fi
        [ -z "$line" ] && { t=$cur; cur=$nxt; nxt=$t; continue; }  # gate closed

        # F5: spool the classifier's SPECIFIC class (its first token). The
        # [help] marker rides WITH a specific class (Decision 1: words follow ->
        # specific class wins), so it must NOT be flattened to sos. "sos" is
        # written only when the class itself IS sos (the wake phrase said alone).
        cls=${line%% *}

        now=$(date +%s)
        if [ "$now" -lt "$cooldown_until" ]; then
            emit "cooldown: ignoring repeat '$cls' (anti double-fire)"
            t=$cur; cur=$nxt; nxt=$t
            continue
        fi

        case "$cls" in
        stop)
            if spool_write stop; then
                emit "CANCELLED -> stop sent to beacon (queue cleared)"
                cooldown_until=$((now + COOLDOWN))
            fi
            ;;
        fire|injured|lost|trapped|sos)
            code=$(code_for "$cls")
            if spool_write "$cls"; then
                emit "EMERGENCY -> $cls ($code) queued to beacon"
                cooldown_until=$((now + COOLDOWN))
            fi
            ;;
        *)
            # uncertain / none: heard a wake-gated command but nothing to send
            emit "heard command, no transmit: $line"
            ;;
        esac
        ;;
    esac

    # swap buffers
    t=$cur; cur=$nxt; nxt=$t
done
