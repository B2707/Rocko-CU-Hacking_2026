### TypeScript
- `strict` stays on; `any` is a smell — use `unknown` + narrowing at boundaries.
- eslint runs on every JS/TS edit (post-write hook) once an eslint config
  exists — a red lint check means fix now, not later. Types are enforced by
  the required CI build-test check (tsc --noEmit), not at edit time.
- No floating promises: await it, or `void` it with a comment saying why;
  try/catch around awaits at system boundaries.
- Immutable by default: spread/map/filter over push/splice on shared data.
- Schema-validate (zod or equivalent) at API boundaries instead of
  hand-rolled checks.
