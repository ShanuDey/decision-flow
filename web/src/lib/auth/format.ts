import type { Method } from "./config";

export function initials(name: string | null | undefined, email: string | null | undefined): string {
  const source = (name?.trim() || email?.split("@")[0] || "").replace(/[^\p{L}\p{N}\s._-]/gu, "");
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const letters = parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0];
  return letters.toUpperCase();
}

const METHOD_LABELS: Record<string, string> = {
  password: "Email and password",
  google: "Google",
  github: "GitHub",
};

const capitalise = (name: string) => name.charAt(0).toUpperCase() + name.slice(1);

export function methodLabel(method: Method): string {
  return METHOD_LABELS[method] ?? capitalise(method);
}

// Better Auth stores the email/password login as the "credential" provider.
export function providerLabel(providerId: string): string {
  return methodLabel(providerId === "credential" ? "password" : providerId);
}

const AUTH_ERRORS: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  account_not_linked: "That email already belongs to another account. Sign in the way you did before.",
  state_mismatch: "That sign-in expired or was started in another browser. Try again.",
  invalid_state: "That sign-in expired or was started in another browser. Try again.",
};

const AUTH_ERROR_FALLBACK = "Sign-in failed. Try again, or ask whoever runs this server to check its log.";

// The code comes from the address bar, so only known codes get their own text and the rest stay generic.
export function authErrorMessage(code: string | string[] | undefined): string | null {
  const value = Array.isArray(code) ? code[0] : code;
  if (!value) return null;
  return AUTH_ERRORS[value] ?? AUTH_ERROR_FALLBACK;
}

