### TypeScript
- `strict` stays on; `any` is a smell — use `unknown` + narrowing at boundaries.
- tsc --noEmit runs on every .ts/.tsx edit (post-write hook) once
  tsconfig.json exists — a red type check means fix now, not later.
- No floating promises: await it, or `void` it with a comment saying why;
  try/catch around awaits at system boundaries.
- Immutable by default: spread/map/filter over push/splice on shared data.
- Schema-validate (zod or equivalent) at API boundaries instead of
  hand-rolled checks.
