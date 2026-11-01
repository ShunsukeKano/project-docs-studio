import { getEnv } from "@/lib/env";

// The browser calls this route; it forwards the request to the API with the writer's own
// Authorization header and passes the answer (a stream) straight back. The API address and the
// model key never reach the browser.
export const dynamic = "force-dynamic";

const MAX_BODY_CHARACTERS = 20_000; // the API limits each field; this only stops absurd requests

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  if (body.length > MAX_BODY_CHARACTERS) {
    return Response.json(
      { error: { code: "validation_error", message: "The request is too large.", details: {} } },
      { status: 413 },
    );
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const authorization = request.headers.get("authorization");
  if (authorization) headers.Authorization = authorization;

  let upstream: Response;
  try {
    upstream = await fetch(`${getEnv().API_BASE_URL}/api/v1/ai/draft`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
      signal: request.signal, // Stop in the browser also stops the model call
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "ai_unavailable",
          message: "The AI draft could not be made. Please try again in a moment.",
          details: {},
        },
      },
      { status: 502 },
    );
  }

  const answer: Record<string, string> = {
    "Content-Type": upstream.headers.get("content-type") ?? "application/json",
    "Cache-Control": "no-store, no-transform",
    "X-Accel-Buffering": "no",
  };
  const retryAfter = upstream.headers.get("retry-after");
  if (retryAfter) answer["Retry-After"] = retryAfter;
  return new Response(upstream.body, { status: upstream.status, headers: answer });
}
