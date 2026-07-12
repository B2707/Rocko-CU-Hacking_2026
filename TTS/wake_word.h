/*
 * Wake-word gate. Only the phrase said AFTER the wake word is classified;
 * everything else is ignored. This is the text-side of "voice activation":
 * Whisper transcribes all speech, and this decides what counts as a command.
 *
 * Change the wake word in one place below. Matching is whole-word and
 * case-insensitive, so "device" fires but "devices" / "mydevice" do not.
 */
#ifndef WAKE_WORD_H
#define WAKE_WORD_H

#include <ctype.h>
#include <string.h>

#define WAKE_WORD "device"    /* must be lowercase */

/*
 * If the wake word appears as a whole word, return a pointer to the start of
 * the phrase that follows it (leading spaces/punctuation skipped). Returns:
 *   - NULL                     if the wake word is not present
 *   - pointer to '\0'          if the wake word is present but nothing follows
 *   - pointer to the phrase    otherwise
 *
 * Uses the FIRST occurrence of the wake word.
 */
static const char *after_wake_word(const char *text) {
    const char *kw = WAKE_WORD;
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
        if (!bound_before || !bound_after) continue;

        /* found it — skip the wake word, then any spaces/punctuation */
        const char *rest = p + klen;
        while (*rest && !isalnum((unsigned char)*rest)) rest++;
        return rest;
    }
    return NULL;
}

#endif /* WAKE_WORD_H */
