const VISITOR_COOKIE = "depitass_visitor";
const YEAR_IN_SECONDS = 60 * 60 * 24 * 365;

export function getVisitor(request: Request) {
  const cookieHeader = request.headers.get("cookie") ?? "";
  const existing = cookieHeader
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${VISITOR_COOKIE}=`))
    ?.slice(VISITOR_COOKIE.length + 1);

  if (existing && /^[a-zA-Z0-9-]{20,80}$/.test(existing)) {
    return { visitorId: existing, isNew: false };
  }

  return { visitorId: crypto.randomUUID(), isNew: true };
}

export function attachVisitorCookie(response: Response, visitorId: string, isNew: boolean) {
  if (isNew) {
    response.headers.append(
      "Set-Cookie",
      `${VISITOR_COOKIE}=${visitorId}; Path=/; Max-Age=${YEAR_IN_SECONDS}; HttpOnly; SameSite=Lax`,
    );
  }
  return response;
}
