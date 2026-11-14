import { getMigrations } from "better-auth/db/migration";

import { retry } from "../retry";
import { PASSWORD } from "./config";
import { asSeed, getAuth, getRuntime, userCount } from "./server";

const SEED_NAME = "Admin";
const MIGRATION_LOCK = 727001;

export async function migrateAuthSchema(): Promise<void> {
  const { options, pool } = getRuntime();
  // The lock makes concurrent cold starts migrate one at a time.
  const lock = await pool.connect();
  try {
    await lock.query("select pg_advisory_lock($1)", [MIGRATION_LOCK]);
    await lock.query("create schema if not exists auth");
    const { runMigrations } = await getMigrations(options);
    await runMigrations();
  } finally {
    await lock.query("select pg_advisory_unlock($1)", [MIGRATION_LOCK]);
    lock.release();
  }
}

export async function seedAdmin(): Promise<void> {
  const { config, pool } = getRuntime();
  const auth = getAuth();
  if (!config.methods.includes(PASSWORD)) return;
  if (!config.adminEmail || !config.adminPassword) {
    if ((await userCount(pool)) === 0) {
      console.warn("auth: password login is on but no account exists; set AUTH_ADMIN_EMAIL and AUTH_ADMIN_PASSWORD");
    }
    return;
  }
  if ((await userCount(pool)) > 0) return;
  const { adminEmail, adminPassword } = config;
  await asSeed(() =>
    auth.api.signUpEmail({ body: { email: adminEmail, password: adminPassword, name: SEED_NAME } }),
  );
  console.log(`auth: seeded the admin account ${config.adminEmail}`);
}

// Both steps are safe to repeat, and the database may still be waking up (Neon suspends when idle).
export async function bootstrapAuth(): Promise<void> {
  const { config } = getRuntime();
  await retry(
    async () => {
      if (config.autoMigrate) await migrateAuthSchema();
      await seedAdmin();
    },
    { onRetry: (error, attempt) => console.warn(`auth: start-up attempt ${attempt} failed, retrying:`, error) },
  );
}
