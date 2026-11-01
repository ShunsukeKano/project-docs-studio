import createClient from "openapi-fetch";

import { getEnv } from "@/lib/env";

import type { paths } from "./generated/schema";

/**
 * A client for the API. The `Authorization` header is passed in for each call (it is simply
 * absent when authentication is off), so no credential lives in a module-level variable.
 * Every request skips the cache.
 */
export function createApiClient(authorization?: string | null) {
  const { API_BASE_URL } = getEnv();
  return createClient<paths>({
    baseUrl: API_BASE_URL,
    cache: "no-store",
    headers: authorization ? { Authorization: authorization } : undefined,
  });
}

export type ApiClient = ReturnType<typeof createApiClient>;

export { toProblem, type ApiProblem } from "./problem";
