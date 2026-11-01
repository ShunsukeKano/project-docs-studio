import { NextResponse, type NextRequest } from "next/server";

/**
 * Writer area gate. When BASIC_AUTH_ENABLED is true, a request to /studio without an
 * Authorization header is answered with a sign-in challenge. This only checks that the header
 * is present: the API is the one place that checks the credentials.
 *
 * The challenge is answered here, on the requested address, rather than by a redirect to
 * /auth/challenge: browsers only send saved credentials to addresses at or below the one that
 * challenged them, so a redirect to another path would loop.
 */
export function proxy(request: NextRequest) {
  if (process.env.BASIC_AUTH_ENABLED !== "true") return NextResponse.next();
  if (request.headers.get("authorization")) return NextResponse.next();
  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="studio"', "Cache-Control": "no-store" },
  });
}

export const config = { matcher: ["/studio/:path*"] };
