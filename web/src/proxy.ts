import { getSessionCookie } from "better-auth/cookies";
import { type NextRequest, NextResponse } from "next/server";

// Optimistic only: the cookie's presence is not proof. Pages and /backend validate the session.
export function proxy(request: NextRequest) {
  if (!getSessionCookie(request)) {
    const login = new URL("/login", request.url);
    const { pathname, search } = request.nextUrl;
    if (pathname !== "/") login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!(?:login|api/auth|backend)(?:/|$)|_next/static|_next/image|favicon\\.ico|icon\\.svg|apple-icon\\.png).*)"],
};
