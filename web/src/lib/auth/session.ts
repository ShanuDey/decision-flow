import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { signApiToken, type TokenUser } from "./api-token";
import { getAuth, getConfig } from "./server";

export async function currentSession() {
  // Read the request first: it marks the page dynamic before any auth setup can throw at build.
  const requestHeaders = await headers();
  return getAuth().api.getSession({ headers: requestHeaders });
}

export async function requireSession() {
  const session = await currentSession();
  if (!session) redirect("/login");
  return session;
}

export function apiToken(user: TokenUser): Promise<string> {
  const { signingKey, issuer, audience } = getConfig();
  return signApiToken(user, { signingKey, issuer, audience });
}

// Request options for the generated client when it runs in a server component.
export async function serverApiInit(): Promise<RequestInit> {
  const { user } = await requireSession();
  return { headers: { Authorization: `Bearer ${await apiToken(user)}` }, cache: "no-store" };
}
