### React / Next.js
- Server components by default; `'use client'` only where state/effects live.
- Hooks: complete dependency arrays, no conditional hooks; derive state
  instead of mirroring it into effects.
- Keys are stable IDs — never the array index on reorderable lists.
- Route handlers that read live state export `dynamic = 'force-dynamic'`,
  or you ship a cached stale API.
- Every fetch gets a loading AND an error state — judges will see the slow path.
