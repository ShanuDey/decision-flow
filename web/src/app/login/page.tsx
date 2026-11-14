import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { connection } from "next/server";

import { PASSWORD } from "@/lib/auth/config";
import { authErrorMessage } from "@/lib/auth/format";
import { safeNext } from "@/lib/auth/redirect";
import { getConfig, hasUsers } from "@/lib/auth/server";
import { currentSession } from "@/lib/auth/session";

import { AuthShell } from "../auth-shell";
import { LoginForm } from "./login-form";
import { WarmUp } from "./warm-up";

export const metadata: Metadata = { title: "Sign in · Decision Flow" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[]; error?: string | string[] }>;
}) {
  await connection();
  const { methods } = getConfig();
  const query = await searchParams;
  const next = safeNext(query.next);
  const error = authErrorMessage(query.error);
  if (await currentSession()) redirect(next);
  const noAccounts = methods.includes(PASSWORD) && !(await hasUsers());

  return (
    <AuthShell title="Sign in">
      {noAccounts && (
        <p role="status" className="text-sm text-muted-foreground">
          No account exists yet. Set AUTH_ADMIN_EMAIL and AUTH_ADMIN_PASSWORD on the server and
          restart it.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <WarmUp />
      <LoginForm methods={methods} next={next} />
    </AuthShell>
  );
}
