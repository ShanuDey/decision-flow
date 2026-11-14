import path from "node:path";

// Real environment variables win over the .env that `make start` generates.
try {
  process.loadEnvFile(path.resolve(__dirname, "..", "..", ".env"));
} catch {
  // no .env: rely on the environment
}

export const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export function adminCredentials(): { email: string; password: string } {
  const email = process.env.AUTH_ADMIN_EMAIL;
  const password = process.env.AUTH_ADMIN_PASSWORD;
  if (!email || !password) {
    throw new Error("AUTH_ADMIN_EMAIL and AUTH_ADMIN_PASSWORD must be set (see the repo-root .env)");
  }
  return { email, password };
}

// Readable and unique, so leftovers are easy to spot and clean.
export const testName = (label: string) => `e2e ${label} ${Date.now()}`;

export const AUTH_FILE = ".auth/admin.json";
