# web

Next.js (App Router) front end: flows list and the flow editor.

```bash
pnpm dev          # http://localhost:3000 (needs the API on NEXT_PUBLIC_API_URL)
pnpm test         # Vitest: graph model (round trip, ids, node rules)
pnpm lint
pnpm exec tsc --noEmit
pnpm build
pnpm generate     # regenerate src/lib/api from ../api/openapi.json (or `make client` at the root)
```

- `src/lib/api/`: generated client and Zod schemas (wiped on every `pnpm generate`, never edit or add files here). `src/lib/call.ts` is the hand-written wrapper around it.
- `src/lib/graph/`: graph JSON types, node rules and React Flow conversion (pure, unit tested).
- `src/components/editor/`: the editor (Zustand store, canvas, palette, settings panel, test run).
- `src/components/ui/`: shadcn/ui components.
