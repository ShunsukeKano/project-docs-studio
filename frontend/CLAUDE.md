# frontend

Next.js 16 (App Router), TypeScript in strict mode, pnpm.
The shared rules (the Spec Kit workflow, `docs/`, the language policy) are in the root `../CLAUDE.md`.

- Types are generated from `../backend/openapi.json` (never edit `src/lib/api/generated/` by hand, and never hand-write the types).
- Reads use Server Components and writes use Server Actions. The URL of the API and any credentials never reach the browser.
- The writer area (`/studio`) uses Basic authentication when `BASIC_AUTH_ENABLED` is true (always in production; off by default for a local run). FastAPI does the checking; Next.js forwards the `Authorization` header and, on a 401, returns `WWW-Authenticate` from a route handler. The public site needs no authentication.
- Public pages are rendered dynamically on every request (`force-dynamic`) and nothing is cached.
- Styling uses Tailwind CSS only (no component library): minimal and stylish, with a neutral palette, one accent colour, system fonts, generous whitespace, visible keyboard focus and responsive layouts. It is a time-boxed polish step done after the functionality and its tests; looks are not assessed.
- Markdown is rendered with one shared renderer and sanitizer (`src/lib/markdown.ts`), used by both the public page and the writer's preview.
- The `Dockerfile` needs `output: "standalone"` in `next.config.ts`.
- `Dockerfile` and `cloudbuild.yaml` are in this folder.
