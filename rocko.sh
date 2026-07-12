#!/bin/sh
#
# rocko.sh - Cave Explorer Safety Beacon (project Rocko), one-program launcher.
#
# ONE command on the Pi that replaces the pile of test scripts (E5). It:
#   (a) brings audio up if the mic is missing (decision 2 - the ONLY sanctioned
#       automatic io-snd restart, and only here, run by the operator),
#   (b) starts the coil transmitter daemon,
#   (c) starts the live listener,
#   (d) merges both into ONE terminal stream where every event line carries a
#       monotonically increasing number [#0001] and a timestamp, mirrored to a
#       size-capped log file.
# One Ctrl+C stops everything with the coil forced off.
#
# Subcommands:
#   rocko.sh            run the beacon (default)
#   rocko.sh run        same as above
#   rocko.sh photo [img] classify one injury photo and exit (E7)
#   rocko.sh help       usage
#
# POSIX sh only (/bin/sh is ksh on QNX 8). No bashisms; syntax-checked with
# `sh -n`. Paths are overridable by env so the same script works if the tree is
# laid out differently on the Pi.

set -u

# --- deployment paths (override via env) --------------------------------
ROCKO_HOME=${ROCKO_HOME:-/data/home/qnxuser}
AUDIO_DIR=${AUDIO_DIR:-$ROCKO_HOME/audio}
CNN_DIR=${CNN_DIR:-$ROCKO_HOME/cnn}

LISTENER=${ROCKO_LISTENER:-$AUDIO_DIR/live_listen_qnx.sh}
TRANSMITTER=${ROCKO_TRANSMITTER:-$ROCKO_HOME/transmitter/transmitter.py}
PHOTO_SCRIPT=${ROCKO_PHOTO:-$CNN_DIR/photo_classify.py}
PHOTO_MODEL=${ROCKO_PHOTO_MODEL:-$CNN_DIR/injury.tflite}
PHOTO_LABELS=${ROCKO_PHOTO_LABELS:-$CNN_DIR/labels.txt}
PHOTO_IMAGE=${ROCKO_PHOTO_IMAGE:-$CNN_DIR/demo.jpg}

PY=${PYTHON:-python3}
MIC_NODE=${MIC_NODE:-/dev/snd/pcmC0D0c}
SND_CONF=${SND_CONF:-/etc/system/config/sound/io_snd.conf}
SPOOL=${BEACON_SPOOL:-/tmp/beacon_trigger}
LOG=${ROCKO_LOG:-/tmp/rocko.log}
ROCKO_PID=${ROCKO_PID:-/tmp/rocko.pid}
LOG_MAX_BYTES=${ROCKO_LOG_MAX_BYTES:-262144}   # 256 KiB before rotate
AUDIO_WAIT=${ROCKO_AUDIO_WAIT:-10}             # seconds to wait for mic node

FIFO=/tmp/rocko.$$.fifo
NUM_PID=""
TX_PID=""
LS_PID=""
CLEANING=""

# --- unified event stream: [#NNNN] timestamp <line>, mirrored to LOG -----
# Reads stdin line by line; ignores INT/TERM so it can drain the final events
# (coil off, SIGNAL SENT) after the producers are told to stop.
numberer() {
    trap '' INT TERM
    n=0
    while IFS= read -r rk_line; do
        n=$((n + 1))
        rk_ts=$(date '+%Y-%m-%d %H:%M:%S')
        rk_out=$(printf '[#%04d] %s %s' "$n" "$rk_ts" "$rk_line")
        printf '%s\n' "$rk_out"
        printf '%s\n' "$rk_out" >> "$LOG" 2>/dev/null || true
    done
}

rotate_log() {
    # E8: cap log growth. Rotate a too-big log aside at startup.
    if [ -f "$LOG" ]; then
        sz=$(wc -c < "$LOG" 2>/dev/null | tr -d ' ')
        [ -z "$sz" ] && sz=0
        if [ "$sz" -gt "$LOG_MAX_BYTES" ]; then
            mv -f "$LOG" "$LOG.1" 2>/dev/null || : > "$LOG"
        fi
    fi
}

# emit one event into the unified numbered stream (fd 3 opened in cmd_run)
emit() { printf '%s\n' "$*" >&3; }

# --- audio bring-up (decision 2, sanctioned ONLY here) ------------------
ensure_audio() {
    if [ -e "$MIC_NODE" ]; then
        emit "audio: mic present ($MIC_NODE)"
        return 0
    fi
    emit "audio: mic node $MIC_NODE absent - bringing io-snd up (decision 2)"
    # The one sanctioned automatic restart: slay io-snd, relaunch from config.
    echo qnxuser | sudo -S sh -c "slay io-snd; io-snd -c $SND_CONF" >&3 2>&3 || \
        emit "ERROR audio bring-up command failed"
    i=0
    while [ ! -e "$MIC_NODE" ] && [ "$i" -lt "$AUDIO_WAIT" ]; do
        sleep 1
        i=$((i + 1))
    done
    if [ -e "$MIC_NODE" ]; then
        emit "audio: mic came up after ${i}s"
    else
        emit "ERROR audio: mic still absent after ${AUDIO_WAIT}s - listener will report and retry"
    fi
}

# --- single-instance guard (E8: refuse double launch) -------------------
acquire_lock() {
    if ( set -C; printf '%s\n' "$$" > "$ROCKO_PID" ) 2>/dev/null; then
        return 0
    fi
    oldpid=$(cat "$ROCKO_PID" 2>/dev/null | tr -d ' ')
    if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then
        echo "rocko already running (pid $oldpid) - refusing double launch" >&2
        return 1
    fi
    printf '%s\n' "$$" > "$ROCKO_PID" 2>/dev/null   # stale pidfile, take over
}

cleanup() {
    [ -n "$CLEANING" ] && return
    CLEANING=1
    emit "shutdown: stopping listener + transmitter (coil forced off)" 2>/dev/null || true
    [ -n "$LS_PID" ] && kill -TERM "$LS_PID" 2>/dev/null
    [ -n "$TX_PID" ] && kill -TERM "$TX_PID" 2>/dev/null
    [ -n "$LS_PID" ] && wait "$LS_PID" 2>/dev/null
    [ -n "$TX_PID" ] && wait "$TX_PID" 2>/dev/null
    # transmitter's SIGTERM handler runs its finally -> driver.all_off(): coil off.
    exec 3>&- 2>/dev/null       # close write end -> numberer drains then EOFs
    [ -n "$NUM_PID" ] && wait "$NUM_PID" 2>/dev/null
    rm -f "$FIFO"
    rm -f "$ROCKO_PID"
    exit 0
}

cmd_run() {
    acquire_lock || exit 1
    rotate_log
    rm -f "$FIFO"
    if ! mkfifo "$FIFO" 2>/dev/null; then
        echo "ERROR cannot create fifo $FIFO" >&2
        rm -f "$ROCKO_PID"
        exit 1
    fi

    numberer < "$FIFO" &
    NUM_PID=$!
    exec 3> "$FIFO"            # hold the write end so the numberer stays up
    trap cleanup INT TERM

    emit "Rocko beacon starting | log=$LOG | spool=$SPOOL"

    # sanity: required programs present (E8: clear error, clean exit)
    if [ ! -f "$TRANSMITTER" ]; then
        emit "ERROR transmitter not found: $TRANSMITTER"
        cleanup
    fi
    if [ ! -f "$LISTENER" ]; then
        emit "ERROR listener not found: $LISTENER"
        cleanup
    fi

    ensure_audio

    # transmitter daemon: bare log format so we own numbering + timestamps.
    "$PY" "$TRANSMITTER" --log-plain --spool "$SPOOL" >&3 2>&3 &
    TX_PID=$!
    emit "transmitter daemon started (pid $TX_PID)"

    # give the daemon a moment to grab the coil lock; if it died, surface it.
    sleep 2
    if ! kill -0 "$TX_PID" 2>/dev/null; then
        emit "ERROR transmitter exited at startup (already running? GPIO missing?)"
        TX_PID=""
        cleanup
    fi

    # live listener: numbered mode so it emits clean single-line events.
    ROCKO_NUMBERED=1 sh "$LISTENER" >&3 2>&3 &
    LS_PID=$!
    emit "listener started (pid $LS_PID)"
    emit "Rocko is live. One Ctrl+C stops everything, coil off."

    # monitor: if either child dies, tear the other down cleanly.
    while kill -0 "$TX_PID" 2>/dev/null && kill -0 "$LS_PID" 2>/dev/null; do
        sleep 1
    done
    emit "a component exited - shutting down"
    cleanup
}

cmd_photo() {
    img=${1:-$PHOTO_IMAGE}
    rotate_log
    if [ ! -f "$PHOTO_SCRIPT" ]; then
        printf 'ERROR photo classifier not found: %s\n' "$PHOTO_SCRIPT" \
            | numberer
        exit 1
    fi
    # single producer -> pipe straight through the numberer.
    {
        "$PY" "$PHOTO_SCRIPT" "$img" \
            --model "$PHOTO_MODEL" --labels "$PHOTO_LABELS" 2>&1
    } | numberer
}

usage() {
    cat <<EOF
rocko.sh - Cave Explorer Safety Beacon (project Rocko)

Usage:
  rocko.sh [run]        start the beacon (audio bring-up + transmitter + listener)
  rocko.sh photo [img]  classify one injury photo and exit (default: $PHOTO_IMAGE)
  rocko.sh help         this message

Every event line is numbered [#NNNN] with a timestamp and mirrored to $LOG.
One Ctrl+C stops the beacon with the coil forced off.
EOF
}

case "${1:-run}" in
    run)
        shift 2>/dev/null || true
        cmd_run
        ;;
    photo)
        shift
        cmd_photo "$@"
        ;;
    help | -h | --help)
        usage
        ;;
    *)
        printf 'unknown command: %s\n\n' "$1" >&2
        usage
        exit 2
        ;;
esac
