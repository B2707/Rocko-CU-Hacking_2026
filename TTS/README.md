# Emergency Intent Classifier (Tier 2)

Text -> emergency class, using TF-IDF + logistic regression. Trains in Python on
your laptop; runs as dependency-free C on the Raspberry Pi 5 / QNX. Designed to
sit behind whisper.cpp: Whisper turns speech into text, this turns text into a
category.

```
mic -> whisper.cpp -> "i'm lost" -> classifier -> {fire, injured, lost, trapped, none}
```

## Files

| File | What it is |
|---|---|
| `emergency_data.csv` | Training data: `text,label` rows. **This is what you edit to improve accuracy.** |
| `train.py` | Trains the model and generates `model.h`. Run on your laptop. |
| `model.h` | Auto-generated. Vocabulary + weights as C arrays. Do not edit by hand. |
| `classifier.c` | The on-device runtime. Pure C, no deps but libm. |
| `verify.py` | Checks the C runtime matches sklearn's probabilities. |
| `Makefile` | Native + QNX build targets. |

## Workflow

### 1. Train (laptop)
```bash
pip install scikit-learn pandas
python3 train.py            # prints CV accuracy, writes model.h
```

### 2. Build + test (laptop)
```bash
make            # native binary
make test       # run sample utterances
echo "i think i broke my ankle" | ./classifier
```

### 3. Improve accuracy
Add rows to `emergency_data.csv` — especially real transcripts from your own
whisper.cpp on the Pi, including its mistakes (train on the noisy text you'll
actually see). Then:
```bash
make retrain    # regenerate model.h and rebuild
```

### 4. Cross-compile for QNX (Pi 5)
```bash
source ~/qnx800/qnxsdp-env.sh    # put qcc on PATH
make qnx                          # produces classifier_qnx
scp classifier_qnx model.h user@pi5:/home/user/
```
`model.h` is compiled into the binary, so `classifier_qnx` is fully
self-contained — nothing else to copy.

### 5. Wire to whisper.cpp
whisper.cpp emits `[timestamps] text`. Strip the prefix and pipe:
```bash
./whisper-cli -m ggml-base.en.bin -f - --no-timestamps \
  | ./classifier_qnx
# or, if timestamps are on:
./whisper-cli ... | sed -E 's/^\[[^]]*\][[:space:]]*//' | ./classifier_qnx
```

## Design notes

- **Confidence threshold** (`CONF_THRESHOLD` in train.py, default 0.60): below it,
  the classifier reports `uncertain` instead of guessing. Raise it to reduce false
  alarms, lower it to catch more. Tune against real data.
- **Reject class `none`:** keeps everyday speech and non-speech (Whisper artifacts
  like `(wind blowing)`) out of the emergency buckets. Keep feeding it examples.
- **Tokenizer parity:** `analyze()` in train.py and `tokenize()` in classifier.c
  MUST stay identical. If you change one, change the other, and re-run verify.py.
- **This is a classifier, not a safety guarantee.** For high-stakes actions,
  add a spoken confirmation ("Did you say you're trapped?") before acting.
