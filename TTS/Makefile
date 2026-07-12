# Emergency classifier build.
#
#   make            native build (your laptop, for testing)
#   make qnx        cross-compile for QNX aarch64 (Raspberry Pi 5)
#   make retrain    regenerate model.h from emergency_data.csv, then build
#   make test       build and run a few sample utterances
#   make clean

CFLAGS = -O2 -Wall -Wextra
LDLIBS = -lm

classifier: classifier.c model.h keyword_override.h wake_word.h
	$(CC) $(CFLAGS) -o $@ classifier.c $(LDLIBS)

# interactive tester: prompts repeatedly, shows full probability breakdown
interactive: interactive.c model.h keyword_override.h wake_word.h
	$(CC) $(CFLAGS) -o $@ interactive.c $(LDLIBS)

# --- QNX cross build ------------------------------------------------------
# Requires the QNX SDP environment sourced first:
#   source ~/qnx800/qnxsdp-env.sh
# That puts qcc / the aarch64 toolchain on PATH.
QNX_CC = qcc -Vgcc_ntoaarch64le
qnx: classifier.c model.h keyword_override.h wake_word.h
	$(QNX_CC) $(CFLAGS) -o classifier_qnx classifier.c -lm

retrain:
	python3 train.py
	$(MAKE) classifier

test: classifier
	@printf '%s\n' \
	  "I'm lost in the woods" \
	  "my arm is broken" \
	  "there's smoke everywhere" \
	  "i'm stuck and can't get out" \
	  "what's the weather today" \
	  | ./classifier --raw

clean:
	rm -f classifier classifier_qnx interactive

.PHONY: qnx retrain test clean
