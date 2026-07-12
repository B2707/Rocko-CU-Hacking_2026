/*
 * Interactive tester for the emergency classifier.
 * Prompts repeatedly, prints the predicted class, confidence, and the full
 * probability breakdown across all classes so you can see how sure it is.
 *
 * Build:  cc -O2 -o interactive interactive.c -lm
 * Run:    ./interactive      (type phrases; 'quit' or Ctrl+D to exit)
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

static int is_tok_char(int c) {
    return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

static int tokenize(const char *text, char toks[][MAX_GRAM]) {
    int n = 0;
    const char *p = text;
    while (*p && n < MAX_TOKENS) {
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
            if (len >= 2) strcpy(toks[n++], buf);
        } else {
            p++;
        }
    }
    return n;
}

static int cmp_key(const void *k, const void *e) {
    return strcmp((const char *)k, ((const VocabEntry *)e)->term);
}
static const VocabEntry *lookup(const char *gram) {
    return (const VocabEntry *)bsearch(gram, VOCAB, NUM_FEATURES,
                                       sizeof(VocabEntry), cmp_key);
}

/* Fill probs[NUM_CLASSES] with softmax probabilities. Returns argmax index. */
static int classify_full(const char *text, double *probs) {
    static float tfidf[NUM_FEATURES];
    memset(tfidf, 0, sizeof(tfidf));

    char toks[MAX_TOKENS][MAX_GRAM];
    int ntok = tokenize(text, toks);

    for (int i = 0; i < ntok; i++) {
        const VocabEntry *v = lookup(toks[i]);
        if (v) tfidf[v->col] += v->idf;
    }
    char gram[2 * MAX_GRAM];
    for (int i = 0; i + 1 < ntok; i++) {
        size_t a = strlen(toks[i]), b = strlen(toks[i + 1]);
        if (a + 1 + b + 1 > sizeof(gram)) continue;
        memcpy(gram, toks[i], a);
        gram[a] = ' ';
        memcpy(gram + a + 1, toks[i + 1], b);
        gram[a + 1 + b] = '\0';
        const VocabEntry *v = lookup(gram);
        if (v) tfidf[v->col] += v->idf;
    }

    double nrm = 0.0;
    for (int j = 0; j < NUM_FEATURES; j++) nrm += (double)tfidf[j] * tfidf[j];
    nrm = sqrt(nrm);
    if (nrm > 0.0)
        for (int j = 0; j < NUM_FEATURES; j++) tfidf[j] = (float)(tfidf[j] / nrm);

    for (int c = 0; c < NUM_CLASSES; c++) {
        double s = INTERCEPT[c];
        for (int j = 0; j < NUM_FEATURES; j++) s += (double)COEF[c][j] * tfidf[j];
        probs[c] = s;
    }
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

/* print a little text bar for a probability in [0,1] */
static void bar(double p) {
    int n = (int)(p * 20.0 + 0.5);
    putchar('[');
    for (int i = 0; i < 20; i++) putchar(i < n ? '#' : ' ');
    putchar(']');
}

int main(void) {
    char line[MAX_LINE];
    double probs[NUM_CLASSES];

    printf("Emergency classifier — interactive tester\n");
    printf("Type a phrase and press Enter. Type 'quit' or Ctrl+D to exit.\n");
    printf("Confidence threshold: %.2f\n", (double)CONF_THRESHOLD);

    for (;;) {
        printf("\n> ");
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin)) { printf("\n"); break; }
        line[strcspn(line, "\r\n")] = '\0';
        if (line[0] == '\0') continue;
        if (strcmp(line, "quit") == 0 || strcmp(line, "exit") == 0) break;

        /* voice-activation gate */
        const char *phrase = after_wake_word(line);
        if (phrase == NULL) {
            printf("  => ignored (no wake word '%s')\n", WAKE_WORD);
            continue;
        }
        if (*phrase == '\0') {
            printf("  => heard '%s' but no phrase followed it\n", WAKE_WORD);
            continue;
        }
        printf("  (activated; classifying: \"%s\")\n", phrase);

        int best = classify_full(phrase, probs);
        int forced = has_emergency_keyword(phrase);

        if (forced) {
            int e = best_emergency_class(probs);
            if (e >= 0) best = e;
            printf("  => %s  (%.0f%%)  [forced by keyword 'help']\n",
                   CLASS_NAMES[best], probs[best] * 100.0);
        } else if (probs[best] < CONF_THRESHOLD) {
            printf("  => UNCERTAIN (top guess: %s, %.0f%%)\n",
                   CLASS_NAMES[best], probs[best] * 100.0);
        } else {
            printf("  => %s  (%.0f%%)\n", CLASS_NAMES[best], probs[best] * 100.0);
        }

        /* full breakdown, highest first (simple selection sort on a copy) */
        int order[NUM_CLASSES];
        for (int i = 0; i < NUM_CLASSES; i++) order[i] = i;
        for (int i = 0; i < NUM_CLASSES; i++)
            for (int j = i + 1; j < NUM_CLASSES; j++)
                if (probs[order[j]] > probs[order[i]]) {
                    int t = order[i]; order[i] = order[j]; order[j] = t;
                }
        for (int i = 0; i < NUM_CLASSES; i++) {
            int c = order[i];
            printf("     %-9s %5.1f%% ", CLASS_NAMES[c], probs[c] * 100.0);
            bar(probs[c]);
            putchar('\n');
        }
    }
    printf("bye\n");
    return 0;
}
