/*
 * Keyword override: certain words force an emergency classification,
 * bypassing the confidence threshold and the "none" class.
 *
 * Add or remove trigger words in EMERGENCY_KEYWORDS below. Matching is
 * whole-word and case-insensitive, so "help" fires on "Help me!" but NOT
 * on "helpful" or "helpless".
 *
 * Shared by classifier.c and interactive.c so behavior stays identical.
 */
#ifndef KEYWORD_OVERRIDE_H
#define KEYWORD_OVERRIDE_H

#include <ctype.h>
#include <string.h>
#include "model.h"

static const char *EMERGENCY_KEYWORDS[] = {
    "help",
    /* add more here, e.g. "emergency", "sos", "mayday", */
};
#define NUM_KEYWORDS (sizeof(EMERGENCY_KEYWORDS) / sizeof(EMERGENCY_KEYWORDS[0]))

/* Whole-word, case-insensitive search for any trigger keyword. */
static int has_emergency_keyword(const char *text) {
    for (size_t k = 0; k < NUM_KEYWORDS; k++) {
        const char *kw = EMERGENCY_KEYWORDS[k];
        size_t klen = strlen(kw);
        for (const char *p = text; *p; p++) {
            size_t i = 0;
            while (i < klen && p[i] &&
                   (char)tolower((unsigned char)p[i]) == kw[i]) i++;
            if (i != klen) continue;
            char before = (p == text) ? ' ' : p[-1];
            char after  = p[klen];
            int bound_before = !isalnum((unsigned char)before);
            int bound_after  = (after == '\0') || !isalnum((unsigned char)after);
            if (bound_before && bound_after) return 1;
        }
    }
    return 0;
}

/* Highest-probability class that is NOT "none". Used when a keyword forces
 * an emergency but we still want the best-guess category. */
static int best_emergency_class(const double *probs) {
    int best = -1;
    for (int c = 0; c < NUM_CLASSES; c++) {
        if (strcmp(CLASS_NAMES[c], "none") == 0) continue;
        if (best < 0 || probs[c] > probs[best]) best = c;
    }
    return best;   /* -1 only if every class is "none", which shouldn't happen */
}

#endif /* KEYWORD_OVERRIDE_H */
