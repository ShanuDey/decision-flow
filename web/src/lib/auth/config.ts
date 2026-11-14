export type Env = Record<string, string | undefined>;

export const PASSWORD = "password";

export type Method = string;

// Option names follow that provider's Better Auth docs (clientId, domain, ...).
export type SocialOptions = Record<string, string | boolean>;

const filled = (value: string | undefined): value is string => !!value && value.trim() !== "";

const list = (value: string | undefined): string[] =>
  (value ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

// "email" and "credential" are what people (and Better Auth) call the password login.
const METHOD_ALIASES: Record<string, string> = { email: PASSWORD, credential: PASSWORD };

export function parseMethods(env: Env): Method[] {
  const requested = list(env.AUTH_METHODS)
    .map((name) => name.toLowerCase())
    .map((name) => METHOD_ALIASES[name] ?? name);
  return requested.length > 0 ? [...new Set(requested)] : [PASSWORD];
}

// Environment values are text; "true" and "false" must reach the provider as booleans, not truthy strings.
const typed = (value: string): string | boolean =>
  value === "true" ? true : value === "false" ? false : value;

const camelCase = (name: string) =>
  name
    .toLowerCase()
    .split("_")
    .map((part, i) => (i === 0 ? part : part.charAt(0).toUpperCase() + part.slice(1)))
    .join("");

// NAME_CLIENT_ID -> clientId, NAME_USER_POOL_ID -> userPoolId; nothing is checked, a bad setup shows in the web server log.
export function socialOptions(env: Env, methods: Method[]): Record<string, SocialOptions> {
  const providers: Record<string, SocialOptions> = {};
  for (const name of methods.filter((m) => m !== PASSWORD)) {
    const prefix = `${name.toUpperCase().replace(/[^A-Z0-9]+/g, "_")}_`;
    providers[name] = Object.fromEntries(
      Object.entries(env)
        .filter(([key, value]) => key.startsWith(prefix) && key.length > prefix.length && filled(value))
        .map(([key, value]) => [camelCase(key.slice(prefix.length)), typed(value!.trim())]),
    );
  }
  return providers;
}

export type DatabaseUrlSource = "AUTH_DATABASE_URL" | "DATABASE_URL";

// The API's DATABASE_URL carries a Python driver prefix (postgresql+psycopg://) that the Node driver rejects.
export function authDatabaseUrl(env: Env): { url: string; source: DatabaseUrlSource } {
  if (filled(env.AUTH_DATABASE_URL)) {
    return { url: env.AUTH_DATABASE_URL.trim(), source: "AUTH_DATABASE_URL" };
  }
  const shared = env.DATABASE_URL?.trim();
  if (shared && /^postgres(?:ql)?(?:\+\w+)?:\/\//.test(shared)) {
    return { url: shared.replace(/^(postgres(?:ql)?)\+\w+:\/\//, "$1://"), source: "DATABASE_URL" };
  }
  throw new Error("AUTH_DATABASE_URL is required: set it, or set DATABASE_URL to a Postgres URL");
}

export interface AuthConfig {
  methods: Method[];
  social: Record<string, SocialOptions>;
  baseURL: string;
  secret: string;
  databaseUrl: string;
  databaseUrlSource: DatabaseUrlSource;
  signingKey: string;
  issuer: string;
  audience: string;
  apiUrl: string;
  autoMigrate: boolean;
  adminEmail: string | undefined;
  adminPassword: string | undefined;
  trustedOrigins: string[];
  allowedDomains: string[];
  ipHeader: string;
  trustedProxies: string[];
}

function origins(value: string | undefined): string[] {
  return list(value).flatMap((entry) => {
    try {
      return [new URL(entry).origin];
    } catch {
      return [];
    }
  });
}

export function domainAllowed(email: string | null | undefined, domains: string[]): boolean {
  if (domains.length === 0) return true;
  const parts = (email ?? "").toLowerCase().split("@");
  return parts.length === 2 && parts[1] !== "" && domains.includes(parts[1]);
}

// Applied to social sign-ups and sign-ins when AUTH_ALLOWED_EMAIL_DOMAINS is set.
export function accountAllowed(
  user: { email?: string | null; emailVerified?: boolean | null } | undefined,
  domains: string[],
): boolean {
  if (domains.length === 0) return true;
  return !!user && user.emailVerified === true && domainAllowed(user.email, domains);
}

function required(env: Env, name: string): string {
  const value = env[name];
  if (!filled(value)) throw new Error(`${name} is required (run \`make auth-setup\`)`);
  return value;
}

export function loadAuthConfig(env: Env): AuthConfig {
  const methods = parseMethods(env);
  const social = socialOptions(env, methods);
  const baseURL = (env.BETTER_AUTH_URL?.trim() || "http://localhost:3000").replace(/\/+$/, "");
  const database = authDatabaseUrl(env);
  return {
    methods,
    social,
    baseURL,
    secret: required(env, "BETTER_AUTH_SECRET"),
    databaseUrl: database.url,
    databaseUrlSource: database.source,
    signingKey: required(env, "AUTH_SIGNING_KEY").replace(/\\n/g, "\n"),
    issuer: env.AUTH_TOKEN_ISSUER?.trim() || baseURL,
    audience: env.AUTH_TOKEN_AUDIENCE?.trim() || "decision-flow-api",
    apiUrl: (env.API_URL?.trim() || "http://localhost:8000").replace(/\/+$/, ""),
    autoMigrate: env.AUTH_AUTO_MIGRATE !== "false",
    adminEmail: filled(env.AUTH_ADMIN_EMAIL) ? env.AUTH_ADMIN_EMAIL : undefined,
    adminPassword: filled(env.AUTH_ADMIN_PASSWORD) ? env.AUTH_ADMIN_PASSWORD : undefined,
    trustedOrigins: origins(env.AUTH_TRUSTED_ORIGINS),
    ipHeader: env.AUTH_IP_HEADER?.trim().toLowerCase() || "x-forwarded-for",
    trustedProxies: list(env.AUTH_TRUSTED_PROXIES),
    allowedDomains: list(env.AUTH_ALLOWED_EMAIL_DOMAINS).map((d) => d.toLowerCase().replace(/^@/, "")),
  };
}
