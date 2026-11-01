import { z } from "zod";

const schema = z.object({
  API_BASE_URL: z.url(),
  BASIC_AUTH_ENABLED: z
    .enum(["true", "false", ""])
    .optional()
    .transform((value) => value === "true"),
});

export type Env = z.infer<typeof schema>;

/**
 * Read and check the server variables when first needed (inside the client factory), not at
 * import time, so `next build` does not need the API address.
 */
export function getEnv(): Env {
  const parsed = schema.safeParse({
    API_BASE_URL: process.env.API_BASE_URL,
    BASIC_AUTH_ENABLED: process.env.BASIC_AUTH_ENABLED,
  });
  if (!parsed.success) {
    throw new Error(`Invalid server configuration: ${z.prettifyError(parsed.error)}`);
  }
  return parsed.data;
}
