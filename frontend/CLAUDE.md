# frontend

Next.js 16 (App Router), TypeScript in strict mode, pnpm.
The shared rules (the Spec Kit workflow, `docs/`, the language policy) are in the root `../CLAUDE.md`.

- Types are generated from `../backend/openapi.json` (never edit `src/lib/api/generated/` by hand, and never hand-write the types).
- Reads use Server Components and writes use Server Actions. The URL of the API and any credentials never reach the browser.
- The writer area (`/studio`) uses Basic authentication when `BASIC_AUTH_ENABLED` is true (always in production; off by default for a local run). FastAPI does the checking; Next.js forwards the `Authorization` header. `src/proxy.ts` answers a missing header with `401` and `WWW-Authenticate` on the requested address itself (a redirect would loop). When the API rejects the credentials, the page goes to `/auth/challenge`, a route handler that **checks the credentials with the API**: it sends the writer back to `/studio` only if the API accepts them, and otherwise answers `401` so the browser asks again (never redirect without that check: a wrong password would loop for ever and the page would stay blank). The public site needs no authentication.
- A new article is written directly in the editor (`/studio/new`, `new-article-form.tsx`): nothing exists until the first save, and the slug follows the title until edited (the slug field holds only the slug). "Save & publish" saves the draft and then publishes the version just saved; if only the publish fails, the screen says the draft was saved.
- Optional AI extra: the "Generate with AI" button (`ai-generate-bar.tsx`) is always visible and is disabled with a note when the server has the feature off. It reads a server-sent stream through the route handler `src/app/(studio)/studio/ai-draft/route.ts` (which passes the browser's `Authorization` header and the stream through, so the API address and the key never reach the browser) and fills only the body field; it never saves, and never changes the title or tags.
- Images are files in `public/images/` served by the app (`next/image` with `unoptimized`). No page loads an image, font or script from another site; `tests/no-external-assets.test.ts` fails if a source file names an image host, and the content security policy allows only the app's own images.
- Every page uses one content width (`max-w-4xl` in both layouts).
- Public pages are rendered dynamically on every request (`force-dynamic`) and nothing is cached.
- Styling uses Tailwind CSS only (no component library): minimal and stylish, with a neutral palette, one accent colour, system fonts, generous whitespace, visible keyboard focus and responsive layouts. It is a time-boxed polish step done after the functionality and its tests; looks are not assessed.
- Markdown is rendered with one shared renderer and sanitizer (`src/lib/markdown.ts`), used by both the public page and the writer's preview.
- The `Dockerfile` needs `output: "standalone"` in `next.config.ts`.
- Real-browser tests are in `e2e/` (Playwright, `playwright.config.ts`); run them with `make e2e` from the repository root, which starts a throwaway system and removes it afterwards (needs Docker and Chrome). They are not part of `pnpm test` (Vitest runs only `tests/`) or `make test`. A test makes its own data through the API with a unique slug, and never clicks "Generate with AI" (the AI feature is off in that system).
- `Dockerfile` and `cloudbuild.yaml` are in this folder. On Google Cloud, pushes to `main` build this `Dockerfile` automatically (a Cloud Build trigger made in the Cloud Run console).
