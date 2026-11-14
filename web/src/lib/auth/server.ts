import { AsyncLocalStorage } from "node:async_hooks";

import { type BetterAuthOptions, betterAuth } from "better-auth";
import { APIError } from "better-auth/api";
import { nextCookies } from "better-auth/next-js";
import { Pool } from "pg";

import { accountAllowed, type AuthConfig, loadAuthConfig, PASSWORD } from "./config";

const SCHEMA = "auth";

interface Runtime {
  config: AuthConfig;
  pool: Pool;
  options: BetterAuthOptions;
  auth?: ReturnType<typeof betterAuth>;
}

let runtime: Runtime | undefined;
let usersExist = false;
const seedScope = new AsyncLocalStorage<true>();

// Marks sign-ups made by the server itself (the env-seeded admin); scoped to the call, not the process.
export function asSeed<T>(work: () => Promise<T>): Promise<T> {
  return seedScope.run(true, work);
}

const refuse = (message: string) => new APIError("FORBIDDEN", { message });

function authOptions(config: AuthConfig, pool: Pool): BetterAuthOptions {
  return {
    appName: "Decision Flow",
    baseURL: config.baseURL,
    secret: config.secret,
    database: pool,
    emailAndPassword: {
      enabled: config.methods.includes(PASSWORD),
      minPasswordLength: 8,
      autoSignIn: true,
    },
    socialProviders: config.social as BetterAuthOptions["socialProviders"],
    rateLimit: {
      enabled: true,
      window: 60,
      max: 100,
      customRules: { "/sign-in/email": { window: 60, max: 10 } },
    },
    session: { cookieCache: { enabled: true, maxAge: 60 } },
    // A social login must never attach to an existing account just because the emails match.
    account: { accountLinking: { enabled: false } },
    // A failed provider login comes back to our login page as ?error=<code>, not Better Auth's own page.
    onAPIError: { errorURL: "/login" },
    advanced: {
      ipAddress: {
        ipAddressHeaders: [config.ipHeader],
        ...(config.trustedProxies.length > 0 && { trustedProxies: config.trustedProxies }),
      },
    },
    databaseHooks: {
      user: {
        create: {
          before: async (user, ctx) => {
            // The seeded admin is trusted by definition, so its email counts as verified.
            if (seedScope.getStore()) return { data: { ...user, emailVerified: true } };
            // Password accounts exist only through the env-seeded admin; public sign-up stays closed.
            if (ctx?.path?.startsWith("/sign-up/email")) throw refuse("Sign-up is closed");
            if (!accountAllowed(user, config.allowedDomains)) throw refuse("This account is not allowed here");
            return { data: user };
          },
        },
      },
      session: {
        create: {
          // The rule also applies to people who signed up before it was set or narrowed.
          before: async (session, ctx) => {
            if (config.allowedDomains.length === 0 || !ctx?.path?.startsWith("/callback")) {
              return { data: session };
            }
            const { rows } = await pool.query<{ email: string; emailVerified: boolean }>(
              'select email, "emailVerified" from "user" where id = $1',
              [session.userId],
            );
            if (!accountAllowed(rows[0], config.allowedDomains)) throw refuse("This account is not allowed here");
            return { data: session };
          },
        },
      },
    },
    plugins: [nextCookies()],
  };
}

export function getRuntime(): Runtime {
  if (!runtime) {
    const config = loadAuthConfig(process.env);
    if (config.databaseUrlSource === "DATABASE_URL") {
      console.info("auth: AUTH_DATABASE_URL is not set, using DATABASE_URL with the auth schema");
    }
    const pool = new Pool({
      connectionString: config.databaseUrl,
      options: `-c search_path=${SCHEMA}`,
      // Serverless starts many instances; keep each one small so a free database is not exhausted.
      max: 3,
      idleTimeoutMillis: 10_000,
    });
    // An idle connection dropped by the database (Neon suspends) must not crash the process.
    pool.on("error", (error) => console.error("auth: database connection error:", error.message));
    runtime = { config, pool, options: authOptions(config, pool) };
  }
  return runtime;
}

// Created on first use, after bootstrap has migrated the schema.
export function getAuth() {
  const rt = getRuntime();
  return (rt.auth ??= betterAuth(rt.options));
}
export const getConfig = () => getRuntime().config;

// Once an account exists there is no need to ask again, so public pages stop querying the database.
export async function hasUsers(pool: Pool = getRuntime().pool): Promise<boolean> {
  if (!usersExist) usersExist = (await userCount(pool)) > 0;
  return usersExist;
}

export async function userCount(pool: Pool = getRuntime().pool): Promise<number> {
  const result = await pool.query<{ n: number }>('select count(*)::int as n from "user"');
  return result.rows[0].n;
}
