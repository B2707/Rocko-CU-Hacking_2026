/*
 * Wake-phrase gate (project Rocko). Only the phrase said AFTER the wake
 * phrase is classified; everything else is ignored. This is the text-side of
 * "voice activation": Whisper transcribes all speech, and this decides what
 * counts as a command. It is the SINGLE choke point — the shell listener pipes
 * raw transcripts straight in and never fabricates a wake word.
 *
 * Wake phrase = "hey rocko help" (decision 1, 2026-07-12). Matching is robust
 * to whisper's variations: case, punctuation, comma splits, and the many ways
 * "rocko" comes back ("rocco", "roko", "rock", ...). The three words must be
 * consecutive tokens (any run of non-alphanumerics may separate them), so a
 * stray "help" or "rocko" in normal speech never opens the gate.
 *
 * Saying the phrase ALONE (nothing meaningful after it) is handled by the
 * caller as SOS — see classifier.c run_one().
 */
#ifndef WAKE_WORD_H
#define WAKE_WORD_H

#include <ctype.h>
#include <string.h>

/* Human-readable phrase for banners/help text (matching is token-based below). */
#define WAKE_PHRASE "hey rocko help"

#define WK_TOK_MAX 32     /* max chars kept per token (spoken words are short) */
#define WK_TOKS_MAX 128   /* max tokens scanned in one transcript line */

/* Read the next alphanumeric token starting at *pp, lowercased into buf.
 * Skips leading non-alnum separators. On success returns 1, sets *tok_end to
 * the first char past the token, and advances *pp. Returns 0 at end of string. */
static int wk_next_token(const char **pp, char *buf, size_t bufsz,
                         const char **tok_end) {
    const char *p = *pp;
    while (*p && !isalnum((unsigned char)*p)) p++;
    if (!*p) { *pp = p; return 0; }
    size_t n = 0;
    while (*p && isalnum((unsigned char)*p)) {
        if (n + 1 < bufsz) {
            char c = *p;
            if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
            buf[n++] = c;
        }
        p++;
    }
    buf[n] = '\0';
    *tok_end = p;
    *pp = p;
    return 1;
}

static int wk_in_set(const char *tok, const char *const *set, size_t n) {
    for (size_t i = 0; i < n; i++)
        if (strcmp(tok, set[i]) == 0) return 1;
    return 0;
}

/* Whisper variants. Kept deliberately tight: a false wake transmits a false
 * alarm, so only near-homophones are accepted. */
static int wk_is_hey(const char *t) {
    static const char *const S[] = {"hey", "hay", "heya"};
    return wk_in_set(t, S, sizeof(S) / sizeof(S[0]));
}
static int wk_is_rocko(const char *t) {
    /* F6: kept deliberately tight - only near-homophones of "rocko". "rock",
     * "rocky", "rockho", "roco" are dropped: casual speech like "hey rocky
     * helps me..." must NOT open the gate and fire a false alarm. */
    static const char *const S[] = {"rocko", "rocco", "roko", "rockoh"};
    return wk_in_set(t, S, sizeof(S) / sizeof(S[0]));
}
static int wk_is_help(const char *t) {
    /* F6: "helps" dropped - "helps" is a common ordinary word, not the cue. */
    static const char *const S[] = {"help", "halp"};
    return wk_in_set(t, S, sizeof(S) / sizeof(S[0]));
}

/*
 * If the wake phrase "hey rocko help" (or a whisper variant) appears as three
 * consecutive stages - one-or-more "hey", then one-or-more "rocko", then
 * one-or-more "help" - return a pointer into the ORIGINAL text at the start of
 * whatever follows (leading separators skipped). Returns:
 *   - NULL              if the wake phrase is not present (gate closed)
 *   - pointer to '\0'   if the phrase is present but nothing follows (SOS)
 *   - pointer to phrase otherwise
 * Uses the FIRST occurrence of the phrase.
 *
 * F6: each stage accepts consecutive DUPLICATES of an accepted token, so a
 * stutter like "hey rocko rocko help" (or "hey hey rocko help") still fires.
 * Only same-stage repeats are collapsed; a stray "help" or "rocko" elsewhere
 * in normal speech never opens the gate.
 */
static const char *after_wake_word(const char *text) {
    char toks[WK_TOKS_MAX][WK_TOK_MAX];
    const char *ends[WK_TOKS_MAX];
    int nt = 0;
    const char *p = text;
    const char *end;
    char buf[WK_TOK_MAX];
    while (nt < WK_TOKS_MAX && wk_next_token(&p, buf, sizeof(buf), &end)) {
        strcpy(toks[nt], buf);
        ends[nt] = end;
        nt++;
    }
    for (int i = 0; i < nt; i++) {
        int j = i;
        int n;
        n = 0;
        while (j < nt && wk_is_hey(toks[j])) { j++; n++; }
        if (n == 0) continue;                 /* need at least one "hey" */
        n = 0;
        while (j < nt && wk_is_rocko(toks[j])) { j++; n++; }
        if (n == 0) continue;                 /* need at least one "rocko" */
        int help_end = -1;
        while (j < nt && wk_is_help(toks[j])) { help_end = j; j++; }
        if (help_end < 0) continue;           /* need at least one "help" */
        const char *rest = ends[help_end];
        while (*rest && !isalnum((unsigned char)*rest)) rest++;
        return rest;
    }
    return NULL;
}

#endif /* WAKE_WORD_H */
