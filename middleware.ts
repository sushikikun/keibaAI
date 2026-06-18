import { NextResponse, type NextRequest } from "next/server";

// TODO(production-blocker): Replace this redirect with a real authenticated
// session check before exposing dashboard routes.
export function middleware(request: NextRequest) {
  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.searchParams.set("next", request.nextUrl.pathname);

  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/dashboard/:path*"]
};
