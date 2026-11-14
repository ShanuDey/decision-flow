import { describe, expect, it } from "vitest";

import {
  accountAllowed,
  authDatabaseUrl,
  domainAllowed,
  loadAuthConfig,
  parseMethods,
  socialOptions,
} from "./config";

const BASE = {
  BETTER_AUTH_SECRET: "s".repeat(32),
  AUTH_DATABASE_URL: "postgresql://u:p@localhost:5432/db",
  AUTH_SIGNING_KEY: "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
};

describe("parseMethods", () => {
  it("defaults to password when AUTH_METHODS is unset or empty", () => {
    expect(parseMethods({})).toEqual(["password"]);
    expect(parseMethods({ AUTH_METHODS: "" })).toEqual(["password"]);
    expect(parseMethods({ AUTH_METHODS: " , " })).toEqual(["password"]);
  });

  it("keeps the order given, ignores case and spaces, and drops duplicates", () => {
    expect(parseMethods({ AUTH_METHODS: " GitHub, password ,github, Google" })).toEqual([
      "github",
      "password",
      "google",
    ]);
  });

  it("lets a deployment leave password out", () => {
    expect(parseMethods({ AUTH_METHODS: "github,google" })).toEqual(["github", "google"]);
  });

  it("treats email and credential as the password login", () => {
    expect(parseMethods({ AUTH_METHODS: "email" })).toEqual(["password"]);
    expect(parseMethods({ AUTH_METHODS: "Credential,github" })).toEqual(["password", "github"]);
  });

  it("does not list the password login twice", () => {
    expect(parseMethods({ AUTH_METHODS: "email,password,credential" })).toEqual(["password"]);
  });
});

describe("socialOptions", () => {
  it("turns NAME_* variables into that provider's options", () => {
    const env = { GITHUB_CLIENT_ID: " id ", GITHUB_CLIENT_SECRET: "secret" };
    expect(socialOptions(env, ["password", "github"])).toEqual({
      github: { clientId: "id", clientSecret: "secret" },
    });
  });

  it("passes any option the provider's docs ask for, in camelCase", () => {
    const env = {
      COGNITO_CLIENT_ID: "a",
      COGNITO_CLIENT_SECRET: "b",
      COGNITO_DOMAIN: "auth.example.com",
      COGNITO_REGION: "eu-west-1",
      COGNITO_USER_POOL_ID: "pool",
    };
    expect(socialOptions(env, ["cognito"]).cognito).toEqual({
      clientId: "a",
      clientSecret: "b",
      domain: "auth.example.com",
      region: "eu-west-1",
      userPoolId: "pool",
    });
  });

  it("passes true and false as booleans, not text", () => {
    const env = {
      GITHUB_CLIENT_ID: "id",
      GITHUB_DISABLE_SIGN_UP: "false",
      GITHUB_DISABLE_IMPLICIT_SIGN_UP: "true",
      GITHUB_SCOPE: "truely",
    };
    expect(socialOptions(env, ["github"]).github).toEqual({
      clientId: "id",
      disableSignUp: false,
      disableImplicitSignUp: true,
      scope: "truely",
    });
  });

  it("does nothing for password alone", () => {
    expect(socialOptions({ GITHUB_CLIENT_ID: "x" }, ["password"])).toEqual({});
  });

  it("does not check that anything is set; Better Auth reports that", () => {
    expect(socialOptions({}, ["github"])).toEqual({ github: {} });
  });

  it("skips empty values and variables that belong to other providers", () => {
    const env = { GITHUB_CLIENT_ID: "id", GITHUB_CLIENT_SECRET: " ", GOOGLE_CLIENT_ID: "g", GITHUB_: "x" };
    expect(socialOptions(env, ["github"])).toEqual({ github: { clientId: "id" } });
  });
});

describe("loadAuthConfig", () => {
  it("starts with password only when AUTH_METHODS is unset", () => {
    const config = loadAuthConfig(BASE);
    expect(config.methods).toEqual(["password"]);
    expect(config.social).toEqual({});
  });

  it("carries the options of the listed providers", () => {
    const config = loadAuthConfig({
      ...BASE,
      AUTH_METHODS: "github",
      GITHUB_CLIENT_ID: "i",
      GITHUB_CLIENT_SECRET: "s",
    });
    expect(config.methods).toEqual(["github"]);
    expect(config.social.github).toEqual({ clientId: "i", clientSecret: "s" });
  });

  it("requires the secret, database url and signing key", () => {
    for (const name of ["BETTER_AUTH_SECRET", "AUTH_DATABASE_URL", "AUTH_SIGNING_KEY"]) {
      const env: Record<string, string | undefined> = { ...BASE, [name]: undefined };
      expect(() => loadAuthConfig(env)).toThrow(name);
    }
  });

  it("applies defaults and unescapes the signing key", () => {
    const config = loadAuthConfig(BASE);
    expect(config.baseURL).toBe("http://localhost:3000");
    expect(config.issuer).toBe("http://localhost:3000");
    expect(config.audience).toBe("decision-flow-api");
    expect(config.apiUrl).toBe("http://localhost:8000");
    expect(config.autoMigrate).toBe(true);
    expect(config.signingKey).toContain("\nabc\n");
  });

  it("trims trailing slashes and honours overrides", () => {
    const config = loadAuthConfig({
      ...BASE,
      BETTER_AUTH_URL: "https://demo.example.com/",
      API_URL: "https://api.example.com//",
      AUTH_TOKEN_ISSUER: "https://issuer.example.com",
      AUTH_AUTO_MIGRATE: "false",
    });
    expect(config.baseURL).toBe("https://demo.example.com");
    expect(config.apiUrl).toBe("https://api.example.com");
    expect(config.issuer).toBe("https://issuer.example.com");
    expect(config.autoMigrate).toBe(false);
  });
});

describe("domainAllowed", () => {
  it("allows everyone when no domains are configured", () => {
    expect(domainAllowed("a@x.com", [])).toBe(true);
    expect(domainAllowed(null, [])).toBe(true);
  });

  it("matches the exact domain, case-insensitively", () => {
    expect(domainAllowed("A@Acme.com", ["acme.com"])).toBe(true);
    expect(domainAllowed("a@evil.com", ["acme.com"])).toBe(false);
    expect(domainAllowed("a@sub.acme.com", ["acme.com"])).toBe(false);
    expect(domainAllowed("a@acme.com.evil.test", ["acme.com"])).toBe(false);
  });

  it("rejects a missing or malformed email", () => {
    for (const email of [null, undefined, "", "no-at-sign", "a@b@acme.com", "a@"]) {
      expect(domainAllowed(email, ["acme.com"])).toBe(false);
    }
  });
});

describe("loadAuthConfig extras", () => {
  it("reads the trusted origins and allowed domains", () => {
    const config = loadAuthConfig({
      ...BASE,
      AUTH_TRUSTED_ORIGINS: "https://a.example.com/, bad, https://b.example.com",
      AUTH_ALLOWED_EMAIL_DOMAINS: "Acme.com, @Partner.org",
    });
    expect(config.trustedOrigins).toEqual(["https://a.example.com", "https://b.example.com"]);
    expect(config.allowedDomains).toEqual(["acme.com", "partner.org"]);
  });

  it("reads the client IP header and trusted proxies", () => {
    const config = loadAuthConfig({
      ...BASE,
      AUTH_IP_HEADER: " X-Vercel-Forwarded-For ",
      AUTH_TRUSTED_PROXIES: "10.0.0.0/8, 172.16.0.1",
    });
    expect(config.ipHeader).toBe("x-vercel-forwarded-for");
    expect(config.trustedProxies).toEqual(["10.0.0.0/8", "172.16.0.1"]);
  });

  it("defaults to no extra origins or domain rule", () => {
    const config = loadAuthConfig(BASE);
    expect(config.ipHeader).toBe("x-forwarded-for");
    expect(config.trustedProxies).toEqual([]);
    expect(config.trustedOrigins).toEqual([]);
    expect(config.allowedDomains).toEqual([]);
  });
});

describe("authDatabaseUrl", () => {
  it("prefers AUTH_DATABASE_URL when it is set", () => {
    const result = authDatabaseUrl({
      AUTH_DATABASE_URL: " postgresql://web:pw@pooler.example.com/db?sslmode=require ",
      DATABASE_URL: "postgresql+psycopg://api:pw@direct.example.com/db",
    });
    expect(result).toEqual({
      url: "postgresql://web:pw@pooler.example.com/db?sslmode=require",
      source: "AUTH_DATABASE_URL",
    });
  });

  it("derives it from DATABASE_URL and drops the Python driver prefix", () => {
    const result = authDatabaseUrl({ DATABASE_URL: "postgresql+psycopg://u:p@db:5432/app?sslmode=require" });
    expect(result).toEqual({ url: "postgresql://u:p@db:5432/app?sslmode=require", source: "DATABASE_URL" });
  });

  it("keeps a plain postgres URL as it is", () => {
    expect(authDatabaseUrl({ DATABASE_URL: "postgresql://u:p@db/app" }).url).toBe("postgresql://u:p@db/app");
    expect(authDatabaseUrl({ DATABASE_URL: "postgres://u:p@db/app" }).url).toBe("postgres://u:p@db/app");
  });

  it("treats an empty AUTH_DATABASE_URL as unset", () => {
    const env = { AUTH_DATABASE_URL: "  ", DATABASE_URL: "postgresql+psycopg://u:p@db/app" };
    expect(authDatabaseUrl(env).source).toBe("DATABASE_URL");
  });

  it("refuses a DATABASE_URL that is not Postgres, so a wrong database is never guessed", () => {
    expect(() => authDatabaseUrl({ DATABASE_URL: "sqlite+aiosqlite:///app.db" })).toThrow(/AUTH_DATABASE_URL is required/);
    expect(() => authDatabaseUrl({ DATABASE_URL: "mysql://u:p@db/app" })).toThrow(/AUTH_DATABASE_URL is required/);
  });

  it("fails when neither is set", () => {
    expect(() => authDatabaseUrl({})).toThrow(/AUTH_DATABASE_URL is required/);
  });

  it("reports where the URL came from in the loaded config", () => {
    const config = loadAuthConfig({
      ...BASE,
      AUTH_DATABASE_URL: undefined,
      DATABASE_URL: "postgresql+psycopg://u:p@db/app",
    });
    expect(config.databaseUrl).toBe("postgresql://u:p@db/app");
    expect(config.databaseUrlSource).toBe("DATABASE_URL");
  });
});

describe("accountAllowed", () => {
  const domains = ["acme.com"];

  it("allows everyone when no domains are configured", () => {
    expect(accountAllowed(undefined, [])).toBe(true);
    expect(accountAllowed({ email: "a@x.com", emailVerified: false }, [])).toBe(true);
  });

  it("needs a verified email in an allowed domain", () => {
    expect(accountAllowed({ email: "a@acme.com", emailVerified: true }, domains)).toBe(true);
    expect(accountAllowed({ email: "a@acme.com", emailVerified: false }, domains)).toBe(false);
    expect(accountAllowed({ email: "a@acme.com", emailVerified: null }, domains)).toBe(false);
    expect(accountAllowed({ email: "a@evil.com", emailVerified: true }, domains)).toBe(false);
  });

  it("refuses a user that cannot be found", () => {
    expect(accountAllowed(undefined, domains)).toBe(false);
  });
});

