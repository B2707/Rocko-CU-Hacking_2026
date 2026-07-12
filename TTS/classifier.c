/*
 * Emergency intent classifier - pure C inference.
 * Reproduces train.py's pipeline exactly:
 *   text -> tokenize (unigrams+bigrams) -> TF-IDF -> softmax logistic regression
 *
 * No dependencies beyond libc + libm. Build:
 *   cc -O2 -o classifier classifier.c -lm
 * Use:
 *   echo "i'm lost in the woods" | ./classifier
 *   ./whisper-cli ... | ./classifier          (pipe transcripts in, one per line)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "model.h"
#include "keyword_override.h"
#include "wake_word.h"

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
static void run_one(const char *text) {
    /* voice-activation gate: only classify the phrase after the wake word */
    const char *phrase = after_wake_word(text);
    if (phrase == NULL || *phrase == '\0')
        return;   /* no wake word (or nothing after it) -> stay silent */

    double probs[NUM_CLASSES];
    int cls = classify(phrase, probs);

    if (has_emergency_keyword(phrase)) {
        int e = best_emergency_class(probs);
        if (e >= 0) cls = e;
        printf("%s (%.2f) [help] | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
    } else if (probs[cls] < CONF_THRESHOLD) {
        printf("uncertain (top=%s %.2f) | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
    } else {
        printf("%s (%.2f) | %s\n", CLASS_NAMES[cls], probs[cls], phrase);
    }
    fflush(stdout);
}

int main(int argc, char **argv) {
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
