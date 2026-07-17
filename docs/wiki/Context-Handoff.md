# Context Handoff

## Current state

- Persistent repository: `~/Desktop/CU-hakcing-2026`
- Branch: `task/receiver-v2`
- Current protocol and transmitter dataset support are implemented.
- The completed 30-frame descending-duty dataset is preserved and checksummed.
- Offline benchmark and fitted GNB model are under the persistent artifact root.
- Transmitter and receiver processes are stopped; bridge pins were forced low.

## Latest conclusion

The covariance-aware analytical coherent LLR decoded all frames at 100%, 50%,
and 25% when provided scheduled or locally searched boundaries. Four separate
16-entry Hamming group-codebook argmax decisions were verified to be exactly
equivalent to the unrestricted 65,536-message SLNN on all 30 frames, while
being much smaller. The experimental LLR-domain joint-Gaussian group decoder
also reached 18/30 but did not outperform the training-free group codebook.
The conventional layered decoder and real-trained GNB were weaker.

Autonomous synchronization and H0 rejection remain limiting: many correctly
decodable 25% frames had encoded-tilde scores below the current 0.8 threshold.
A first Duong gain-whitening prototype preserved 18/30 decoding and raised
threshold-crossing correct frames from 12/30 to 16/30, but was numerically
indistinguishable from static ZCA and became mismatched on the reserved portion
of the nonstationary ten-minute noise run. It is therefore only a promising
synchronization-weighting observation, not a demonstrated neural advantage.
10% and 1% remained below the recoverable range.

## Next work

1. Improve acquisition without using the known payload or tuning on test data.
2. Calibrate H0 and confidence thresholds from complete silent gaps.
3. Evaluate frequency/timing search with fixed predeclared bounds.
4. Consider a joint whitened matched filter using the raw cross-spectral noise
   matrix rather than only a 2x2 post-match covariance.
5. Preserve an untouched future physical dataset for final confirmation.

## Compaction

This wiki is the durable source of truth. After committing it and the live
viewer/monitor utilities, compact the active agent context and retain only this
handoff plus the latest benchmark artifact paths.
