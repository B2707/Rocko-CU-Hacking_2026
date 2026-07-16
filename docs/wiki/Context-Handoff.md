# Context Handoff

## Current state

- Persistent repository: `~/Desktop/CU-hakcing-2026`
- Branch: `task/receiver-v2`
- Current protocol and transmitter dataset support are implemented.
- The completed 30-frame descending-duty dataset is preserved and checksummed.
- Offline benchmark and fitted GNB model are under the persistent artifact root.
- Transmitter and receiver processes are stopped; bridge pins were forced low.

## Latest conclusion

The covariance-aware analytical coherent LLR followed by full/restricted SLNN
codebook scoring is the strongest tested decoder. It decoded all frames at
100%, 50%, and 25% when provided scheduled boundaries. The conventional
layered decoder decoded fewer 25% frames, while the real-trained GNB did not
improve held-out performance.

Autonomous synchronization and H0 rejection remain limiting: many correctly
decodable 25% frames had encoded-tilde scores below the current 0.8 threshold.
10% and 1% were below the recoverable range in this placement.

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
