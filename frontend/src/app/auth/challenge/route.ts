// A route handler can set WWW-Authenticate; a Server Action cannot. The studio sends the
// browser here when the API rejects the saved credentials, so it asks for them again.
export const dynamic = "force-dynamic";

export function GET(request: Request) {
  if (request.headers.get("authorization")) {
    return new Response(null, { status: 303, headers: { Location: "/studio" } });
  }
  return new Response("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="studio"', "Cache-Control": "no-store" },
  });
}
