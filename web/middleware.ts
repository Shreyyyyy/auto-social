import {NextRequest, NextResponse} from "next/server";

// Optional password gate for the whole studio (pages, /api, /media). Set STUDIO_PASSWORD to turn it on -
// do this before exposing the studio beyond your own computer: it can post to your channels and spend API credit.
// The browser shows its own sign-in box; any username works.
// On Vercel the API is your Mac behind a tunnel: a password is required and API_TOKEN is added to every proxied request.
export function middleware(req: NextRequest) {
  const pass = process.env.STUDIO_PASSWORD;
  const forward = () => {
    const headers = new Headers(req.headers);
    if (process.env.API_TOKEN) headers.set("x-api-token", process.env.API_TOKEN);
    return NextResponse.next({request: {headers}});
  };
  if (!pass) return process.env.VERCEL ? new NextResponse("Set STUDIO_PASSWORD in Vercel first", {status: 503}) : forward();
  const [scheme, value] = (req.headers.get("authorization") || "").split(" ");
  if (scheme === "Basic" && value) {
    const given = atob(value).split(":").slice(1).join(":");
    if (given === pass) return forward();
  }
  return new NextResponse("Sign in required", {status: 401, headers: {"WWW-Authenticate": 'Basic realm="Katha"'}});
}

export const config = {matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg|apple-icon.png|icon-512.png|manifest.webmanifest).*)"]};
