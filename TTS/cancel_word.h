/*
 * Cancel words: a wake-gated "stop" / "cancel" / "clear" / "ok" / "okay"
 * cancels the beacon's emergency queue. This wins over any classifier hit in
 * the same phrase (an explicit "I'm okay" must never be read as an emergency).
 *
 * Matching is whole-word and case-insensitive over the ALREADY-GATED phrase
 * (the text after the wake phrase), so it inherits the single choke point:
 * "stop" only cancels when preceded by "hey rocko help". These tokens mirror
 * transmitter.py's STOP_TOKENS so the surface side reads the same intent.
 */
#ifndef CANCEL_WORD_H
#define CANCEL_WORD_H

#include <ctype.h>
#include <string.h>

static const char *CANCEL_WORDS[] = {
    "stop", "cancel", "clear", "ok", "okay",
};
#define NUM_CANCEL_WORDS (sizeof(CANCEL_WORDS) / sizeof(CANCEL_WORDS[0]))

/*
 * Grammar filler the tiny TF-IDF model over-fits: on its own "am" leans an
 * emergency class (~0.73 "lost"), so a bare "i am okay" would look like an
 * emergency even after the cancel word is removed. Dropping this filler -
 * together with the cancel words - lets the F1 gate ask "is there STILL an
 * emergency word here?" without the filler manufacturing a phantom one. These
 * are pure grammar words; none is ever an emergency, so removing them can only
 * fail safe (a real emergency word always survives and re-classifies).
 */
static const char *FILLER_WORDS[] = {
    "am", "is", "are", "was", "were", "be", "been", "being",
    "the", "a", "an", "my", "me", "i",
};
#define NUM_FILLER_WORDS (sizeof(FILLER_WORDS) / sizeof(FILLER_WORDS[0]))

static int cw_word_in_list(const char *tok, const char *const *list, size_t n) {
    for (size_t i = 0; i < n; i++)
        if (strcmp(tok, list[i]) == 0) return 1;
    return 0;
}

/* Whole-word, case-insensitive search for any cancel word. */
static int has_cancel_keyword(const char *text) {
    for (size_t k = 0; k < NUM_CANCEL_WORDS; k++) {
        const char *kw = CANCEL_WORDS[k];
        size_t klen = strlen(kw);
        for (const char *p = text; *p; p++) {
            size_t i = 0;
            while (i < klen && p[i] &&
                   (char)tolower((unsigned char)p[i]) == kw[i]) i++;
            if (i != klen) continue;
            char before = (p == text) ? ' ' : p[-1];
            char after = p[klen];
            int bound_before = !isalnum((unsigned char)before);
            int bound_after = (after == '\0') || !isalnum((unsigned char)after);
            if (bound_before && bound_after) return 1;
        }
    }
    return 0;
}

/*
 * Copy `text` into `out` (bounded), lowercasing and keeping only the tokens
 * that are NEITHER a cancel word NOR grammar filler; kept tokens are rejoined
 * with single spaces. The result is what remains once the cancel intent and
 * filler are gone - so the F1 gate can classify it and decide whether real
 * emergency content is present. `out` is always NUL-terminated.
 */
static void strip_cancel_and_filler(const char *text, char *out, size_t outsz) {
    size_t oi = 0;
    const char *p = text;
    char tok[64];
    if (outsz) out[0] = '\0';
    while (*p) {
        while (*p && !isalnum((unsigned char)*p)) p++;  /* skip separators */
        if (!*p) break;
        size_t n = 0;
        while (*p && isalnum((unsigned char)*p)) {
            char c = *p;
            if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
            if (n + 1 < sizeof(tok)) tok[n++] = c;
            p++;
        }
        tok[n] = '\0';
        if (cw_word_in_list(tok, CANCEL_WORDS, NUM_CANCEL_WORDS)) continue;
        if (cw_word_in_list(tok, FILLER_WORDS, NUM_FILLER_WORDS)) continue;
        if (oi + (oi ? 1 : 0) + n + 1 > outsz) break;  /* keep it bounded */
        if (oi > 0) out[oi++] = ' ';
        memcpy(out + oi, tok, n);
        oi += n;
        out[oi] = '\0';
    }
}

#endif /* CANCEL_WORD_H */
