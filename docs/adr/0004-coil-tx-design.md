# Transmit coil: ~150 turns on a 10–15 cm former at 12 V

Decided 2026-07-11 (regrill R10). The coil is wound fresh: ~150 turns of the mandated 0.25 mm (AWG30) copper wire on a 10–15 cm-radius non-conductive former, driven by the L298N from a 12 V supply (supply is a new parts-run item, no battery/PSU was in any earlier list).

Why not more turns: at fixed voltage the field plateaus, each added turn raises resistance exactly as fast as it adds loop area, so beyond ~100–200 turns (where wire resistance, not the 0.5 A AWG30 ampacity, limits current) extra turns buy nothing. Radius is the real lever: computed field at 1.5 m is ≈37 nT (5 cm), ≈74 nT (10 cm), ≈112 nT (15 cm); dissipation ~2–3 W. If bench range disappoints, the honest upgrades are a bigger former or a higher-voltage supply (L298N tolerates up to 46 V; field scales linearly with V), not more wire.
