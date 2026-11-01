import type { ApiProblem } from "@/lib/api/server-client";

/** What every Server Action returns, so the screen never has to guess. */
export type ActionResult<T> = { ok: true; data: T } | { ok: false; problem: ApiProblem };
