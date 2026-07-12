# Rocko — Pi deployment map (hardening v2)

How the explorer-side files land on the QNX Pi 5 (`qnxpi17`, `ssh qnxpi`).
Deployment happens later, separately — this is the map, not a run.

## File → Pi path → build step

| Repo file | Pi path | Pi-side build? |
|-----------|---------|----------------|
| `rocko.sh` | `/data/home/qnxuser/rocko.sh` | none (POSIX sh; `sh -n` clean) |
| `TTS/live_listen_qnx.sh` | `/data/home/qnxuser/audio/live_listen_qnx.sh` | none (POSIX sh) |
| `TTS/classifier.c` | `/data/home/qnxuser/audio/classifier.c` | **yes** — `make classifier` in `/data/home/qnxuser/audio` (clang, native) |
| `TTS/wake_word.h` | `/data/home/qnxuser/audio/wake_word.h` | compiled into `classifier` |
| `TTS/cancel_word.h` | `/data/home/qnxuser/audio/cancel_word.h` | compiled into `classifier` |
| `TTS/keyword_override.h` | `/data/home/qnxuser/audio/keyword_override.h` | compiled into `classifier` |
| `TTS/model.h` | `/data/home/qnxuser/audio/model.h` | compiled into `classifier` |
| `TTS/Makefile` | `/data/home/qnxuser/audio/Makefile` | drives `make classifier` |
| `transmitter/transmitter.py` | `/data/home/qnxuser/transmitter/transmitter.py` | none (python3; `python3 -m py_compile` to check) |
| `photo/photo_classify.py` | `/data/home/qnxuser/cnn/photo_classify.py` | none (python3) |
| `photo/labels.txt` | `/data/home/qnxuser/cnn/labels.txt` | none |

## Not in the repo — dropped onto the Pi separately

| Pi path | What | Source |
|---------|------|--------|
| `/data/home/qnxuser/cnn/injury.tflite` | ~16 MB converted EfficientNet-B0 | separate conversion of `CNN/outputs/best_model.pt` |
| `/data/home/qnxuser/cnn/demo.jpg` | default demo photo | `CNN/test_data/` |
| `/data/home/qnxuser/whisper.cpp/...` | whisper-cli + `ggml-tiny.en.bin` | already on the Pi |

## One-time Pi setup

```sh
# AI runtime for the photo demo (satisfies the oss.qnx.com requirement)
apk add python3-tflite-runtime      # plus numpy + Pillow available to python3

# build the audio classifier natively
cd /data/home/qnxuser/audio && make classifier
```

## Build steps summary

- **Only one Pi-side build:** `make classifier` in `/data/home/qnxuser/audio`
  (native clang). Everything else is interpreted (POSIX sh / python3) and needs
  no compilation. Do NOT cross-compile from the laptop.
- Syntax-check before shipping: `sh -n rocko.sh`, `sh -n live_listen_qnx.sh`,
  `python3 -m py_compile transmitter.py photo_classify.py`.

## Run (operator, on the Pi — not part of this task)

```sh
sh /data/home/qnxuser/rocko.sh          # full beacon
sh /data/home/qnxuser/rocko.sh photo    # injury-photo demo
```

Path overrides (if the tree differs) are env vars read by `rocko.sh`:
`ROCKO_HOME`, `AUDIO_DIR`, `CNN_DIR`, `ROCKO_LISTENER`, `ROCKO_TRANSMITTER`,
`ROCKO_PHOTO`, `ROCKO_PHOTO_MODEL`, `ROCKO_PHOTO_LABELS`, `ROCKO_PHOTO_IMAGE`.
