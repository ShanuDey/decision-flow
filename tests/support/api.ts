import { type APIRequestContext, expect, request } from "@playwright/test";

import { adminCredentials, baseURL } from "./env";

// Unsafe methods need a same-origin Origin header, which the web proxy checks.
export async function signedInApi(): Promise<APIRequestContext> {
  const { email, password } = adminCredentials();
  const api = await request.newContext({
    baseURL,
    extraHTTPHeaders: { origin: baseURL },
  });
  const response = await api.post("/api/auth/sign-in/email", { data: { email, password } });
  expect(response.ok(), "sign in through Better Auth").toBeTruthy();
  return api;
}

export const backend = (path: string) => `/backend${path}`;
