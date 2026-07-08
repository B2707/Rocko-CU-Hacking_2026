### All stacks (always stamped)
- Small PRs on the demo path merge fastest: one issue → one branch → one PR.
  The bot blocks only correctness (bugs, broken demo path, data loss,
  security, required red tests) — style never blocks, so don't gold-plate.
- Validate at boundaries: every user input, API response, and file read gets
  checked before use; fail fast with a clear message.
- No secrets in code, config, or logs — env vars only; `.env` stays gitignored.
- Errors are handled or surfaced, never swallowed. A silent catch is a
  demo-day landmine.
- Prefer boring: stdlib > small proven dep > new framework. Every new
  dependency added under 48h to demo is judge-facing risk.
- Names say what things are; magic numbers become constants; functions stay
  under ~50 lines.
