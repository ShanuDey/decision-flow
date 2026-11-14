import { toNextJsHandler } from "better-auth/next-js";

import { getAuth } from "@/lib/auth/server";

// Built per request so a plain `next build` does not need the auth environment.
export const GET = (request: Request) => toNextJsHandler(getAuth()).GET(request);
export const POST = (request: Request) => toNextJsHandler(getAuth()).POST(request);
