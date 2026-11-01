import { getEnv } from "@/lib/env";

// A route handler can set WWW-Authenticate; a Server Action cannot. The studio sends the browser
// here when the API rejected the credentials it was given, so this is where it is asked again.
//
// This route checks the credentials with the API itself. Without that check, a wrong password would
// be "accepted" here, sent back to /studio, rejected again, and sent here again, for ever: the
// browser would stop with "Throttling navigation" and show a blank page.
export const dynamic = "force-dynamic";

const challenge = () =>
  new Response("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="studio"', "Cache-Control": "no-store" },
  });

export async function GET(request: Request): Promise<Response> {
  const authorization = request.headers.get("authorization");
  if (!authorization) return challenge();

  let accepted: boolean;
  try {
    const response = await fetch(`${getEnv().API_BASE_URL}/api/v1/articles?limit=1`, {
      headers: { Authorization: authorization },
      cache: "no-store",
    });
    accepted = response.ok;
  } catch {
    return new Response("The service is not available. Please try again in a moment.", {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }

  // Wrong credentials: ask again (the browser shows its sign-in box). Right ones: go to the studio.
  return accepted
    ? new Response(null, { status: 303, headers: { Location: "/studio", "Cache-Control": "no-store" } })
    : challenge();
}
