import { createApiClient } from "./server-client";

/** Is AI drafting switched on? Any failure counts as "off": the feature is an optional extra. */
export async function isAiDraftingOn(authorization: string | null): Promise<boolean> {
  try {
    const { data } = await createApiClient(authorization).GET("/api/v1/ai/status");
    return data?.enabled === true;
  } catch {
    return false;
  }
}
