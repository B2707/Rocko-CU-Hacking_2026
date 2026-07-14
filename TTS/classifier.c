/*
 * Emergency intent classifier - pure C inference.
 * Reproduces train.py's pipeline exactly:
 *   text -> tokenize (unigrams+bigrams) -> TF-IDF -> softmax logistic regression
 *
 * No dependencies beyond libc + libm. Build:
 *   cc -O2 -o classifier classifier.c -lm
 * Use:
 *   echo "hey rocko help i'm lost" | ./classifier   (wake-phrase gated)
 *   echo "i'm lost in the woods"   | ./classifier --raw  (no wake gate)
 *   ./whisper-cli ... | ./classifier          (pipe transcripts in, one per line)
 *
 * The wake gate here is the SINGLE choke point: a line without "hey rocko help"
 * produces NO output, so the shell listener writes nothing to the beacon spool
 * and nothing transmits. The wake phrase said alone -> "sos". A wake-gated
 * cancel word (stop/cancel/ok) -> "stop", but ONLY when the phrase has no
 * negator and no surviving emergency content (rules 1-2 in run_one); a negated
 * or unclear distress call after the wake phrase escalates to "sos", never
 * cancels and never falls silent (rule 3).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "model.h"
#include "keyword_override.h"
#include "wake_word.h"
#include "cancel_word.h"

/* NOTE: train.py's analyze() has no token/line caps; these bounds are an
 * intentional C-side divergence, spoken commands are short, and anything
 * past 64 tokens contributes almost nothing after L2 normalization. */
#define MAX_TOKENS 64
#define MAX_GRAM   160
#define MAX_LINE   1024

/* ---- Tokenizer: MUST match analyze() in train.py -------------------- */
static int is_tok_char(int c) {
    return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

/* Fill toks[] with lowercased tokens (len>=2). Returns token count. */
static int tokenize(const char *text, char toks[][MAX_GRAM]) {
    int n = 0;
    const char *p = text;
    while (*p && n < MAX_TOKENS) {
        /* lowercase current char for classification */
        char c = *p;
        if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
        if (is_tok_char((unsigned char)c)) {
            int len = 0;
            char buf[MAX_GRAM];
            while (*p && len < MAX_GRAM - 1) {
                char cc = *p;
                if (cc >= 'A' && cc <= 'Z') cc = (char)(cc + 32);
                if (!is_tok_char((unsigned char)cc)) break;
                buf[len++] = cc;
                p++;
            }
            buf[len] = '\0';
            if (len >= 2) {           /* drop 1-char tokens, matching Python */
                strcpy(toks[n++], buf);
            }
        } else {
            p++;
        }
    }
    return n;
}

/* ---- Vocabulary lookup (binary search over sorted VOCAB) ------------ */
static int cmp_key(const void *k, const void *e) {
    return strcmp((const char *)k, ((const VocabEntry *)e)->term);
}

static const VocabEntry *lookup(const char *gram) {
    return (const VocabEntry *)bsearch(
        gram, VOCAB, NUM_FEATURES, sizeof(VocabEntry), cmp_key);
}

/* ---- Core: text -> fills probs[NUM_CLASSES], returns argmax index --- */
int classify(const char *text, double *probs) {
    static float tfidf[NUM_FEATURES];
    memset(tfidf, 0, sizeof(tfidf));

    char toks[MAX_TOKENS][MAX_GRAM];
    int ntok = tokenize(text, toks);

    /* accumulate tf*idf for unigrams */
    for (int i = 0; i < ntok; i++) {
        const VocabEntry *v = lookup(toks[i]);
        if (v) tfidf[v->col] += v->idf;   /* tf increments by 1 -> add idf */
    }
    /* bigrams: "tokA tokB" built with explicit bounded copies */
    char gram[2 * MAX_GRAM];   /* room for two full tokens + space + NUL */
    for (int i = 0; i + 1 < ntok; i++) {
        size_t a = strlen(toks[i]), b = strlen(toks[i + 1]);
        if (a + 1 + b + 1 > sizeof(gram)) continue;   /* can't match vocab anyway */
        memcpy(gram, toks[i], a);
        gram[a] = ' ';
        memcpy(gram + a + 1, toks[i + 1], b);
        gram[a + 1 + b] = '\0';
        const VocabEntry *v = lookup(gram);
        if (v) tfidf[v->col] += v->idf;
    }

    /* L2 normalize (matches TfidfVectorizer norm='l2') */
    double nrm = 0.0;
    for (int j = 0; j < NUM_FEATURES; j++) nrm += (double)tfidf[j] * tfidf[j];
    nrm = sqrt(nrm);
    if (nrm > 0.0)
        for (int j = 0; j < NUM_FEATURES; j++) tfidf[j] = (float)(tfidf[j] / nrm);

    /* linear scores */
    for (int c = 0; c < NUM_CLASSES; c++) {
        double s = INTERCEPT[c];
        const float *w = COEF[c];
        for (int j = 0; j < NUM_FEATURES; j++) s += (double)w[j] * tfidf[j];
        probs[c] = s;
    }

    /* softmax -> probabilities */
    double mx = probs[0];
    for (int c = 1; c < NUM_CLASSES; c++) if (probs[c] > mx) mx = probs[c];
    double sum = 0.0;
    for (int c = 0; c < NUM_CLASSES; c++) { probs[c] = exp(probs[c] - mx); sum += probs[c]; }

    int best = 0;
    for (int c = 0; c < NUM_CLASSES; c++) {
        probs[c] /= sum;
        if (probs[c] > probs[best]) best = c;
    }
    return best;
}

/* ---- CLI: classify each stdin line, or a single argv string --------- */

/* --raw: skip the wake-word gate and classify the text as-is. Used by
 * make test / verify.py / README examples; the live mic path stays gated. */
static int raw_mode = 0;

static void run_one(const char *text) {
    /* Voice-activation gate (single choke point): only the phrase after the
     * wake phrase is classified. In raw mode the gate is skipped (test only). */
    const char *phrase;
    if (raw_mode) {
        phrase = text;
        if (*phrase == '\0')
            return;   /* empty raw input -> nothing to classify */
    } else {
        phrase = after_wake_word(text);
        if (phrase == NULL)
            return;   /* no wake phrase -> gate closed, stay silent */
        if (*phrase == '\0') {
            /* wake phrase said ALONE -> SOS (decision 1) */
            printf("sos (1.00) | %s\n", phrase);
            fflush(stdout);
            return;
        }
        /* Cancel-vs-distress resolution (2026-07-12 hardening, rules 1-2).
         *
         * Rule 1 - negator guard: if the wake-gated phrase contains ANY negator
         * ("not", "no", "nothing", "cannot", ...), the cancel branch is DISABLED
         * entirely. A negated statement ("i am not okay", "nothing is okay") is
         * distress, never a call-off; we fall through to classification (and, if
         * unclear, the SOS fallback below). This closes the false-cancel bug
         * where the cancel word survived stripping while the negator did not.
         *
         * Rule 2 - cancel wins narrowly: with no negator, a cancel token cancels
         * ONLY when the cancel/filler-stripped remainder is EMPTY or its top-1
         * class is "none" (at ANY confidence). A remainder whose top-1 is any
         * emergency class - even below the confidence threshold - must NOT
         * cancel. An explicit emergency keyword ("help") also blocks the cancel.
         * So "i am okay" cancels, but "i fell okay" (remainder top-1 injured)
         * and "i am trapped okay" (remainder top-1 trapped) do not. */
        if (!has_negator(phrase) && has_cancel_keyword(phrase)) {
            char remainder[MAX_LINE];
            strip_cancel_and_filler(phrase, remainder, sizeof(remainder));
            int cancel;
            if (remainder[0] == '\0') {
                cancel = 1;                 /* nothing left but the cancel word */
            } else {
                double rprobs[NUM_CLASSES];
                int rcls = classify(remainder, rprobs);
                cancel = (strcmp(CLASS_NAMES[rcls], "none") == 0);
            }
            if (has_emergency_keyword(phrase)) cancel = 0;
            if (cancel) {
                printf("stop (1.00) | %s\n", phrase);
                fflush(stdout);
                return;
            }
            /* not a cancel -> fall through to normal classification */
        }
    }

    double probs[NUM_CLASSES];
    int cls = classify(phrase, probs);

    if (has_emergency_keyword(phrase)) {
        int e = best_emergency_class(probs);
        if (e >= 0) cls = e;
        printf("%s (%.2f) [help] | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
    } else if (probs[cls] < CONF_THRESHOLD) {
        /* Rule 3 - SOS fallback (wake-gated path only): the speaker said the
         * full wake phrase and then something, but the content is not a
         * confident emergency and did not cancel. Unclear distress must
         * transmit SOS, never fall silent; the [unclear] marker records why.
         * Raw mode (test/verify path, no wake context) keeps the plain
         * "uncertain" report - there is no distress to escalate there. */
        if (raw_mode)
            printf("uncertain (top=%s %.2f) | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
        else
            printf("sos (1.00) [unclear] | %s\n", phrase);
    } else {
        printf("%s (%.2f) | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
    }
    fflush(stdout);
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--raw") == 0) {
        raw_mode = 1;
        argv++;
        argc--;
    }
    if (argc > 1) {                       /* classify the argument */
        char joined[MAX_LINE] = {0};
        for (int i = 1; i < argc; i++) {
            strncat(joined, argv[i], sizeof(joined) - strlen(joined) - 2);
            if (i + 1 < argc) strncat(joined, " ", 2);
        }
        run_one(joined);
        return 0;
    }
    char line[MAX_LINE];                  /* else read stdin line by line */
    while (fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        if (line[0]) run_one(line);
    }
    return 0;
}
