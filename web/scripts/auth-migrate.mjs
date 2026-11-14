// The web server migrates at start unless AUTH_AUTO_MIGRATE=false; this is the manual way.
import path from "node:path";

import nextEnv from "@next/env";
import { getMigrations } from "better-auth/db/migration";
import pg from "pg";

nextEnv.loadEnvConfig(path.resolve(process.cwd(), ".."), false, console, true);

// Same rule as src/lib/auth/config.ts: AUTH_DATABASE_URL, else DATABASE_URL without its Python driver prefix.
const shared = process.env.DATABASE_URL?.trim();
const url =
  process.env.AUTH_DATABASE_URL?.trim() ||
  (shared && /^postgres(?:ql)?(?:\+\w+)?:\/\//.test(shared)
    ? shared.replace(/^(postgres(?:ql)?)\+\w+:\/\//, "$1://")
    : undefined);
if (!url) {
  console.error("Set AUTH_DATABASE_URL, or DATABASE_URL to a Postgres URL");
  process.exit(1);
}

const MIGRATION_LOCK = 727001;
const pool = new pg.Pool({ connectionString: url, options: "-c search_path=auth", max: 4 });
const lock = await pool.connect();
try {
  await lock.query("select pg_advisory_lock($1)", [MIGRATION_LOCK]);
  await lock.query("create schema if not exists auth");
  const { runMigrations } = await getMigrations({
    database: pool,
    emailAndPassword: { enabled: true },
  });
  await runMigrations();
  console.log("auth schema is up to date");
} finally {
  await lock.query("select pg_advisory_unlock($1)", [MIGRATION_LOCK]);
  lock.release();
  await pool.end();
}
