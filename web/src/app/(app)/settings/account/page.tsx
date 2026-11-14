import type { Metadata } from "next";
import { headers } from "next/headers";

import { providerLabel } from "@/lib/auth/format";
import { getAuth } from "@/lib/auth/server";
import { requireSession } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Account · Decision Flow" };

export default async function AccountPage() {
  const requestHeaders = await headers();
  const { user } = await requireSession();
  const accounts = await getAuth().api.listUserAccounts({ headers: requestHeaders });
  const methods = accounts.map((a) => providerLabel(a.providerId)).join(", ") || "Unknown";

  return (
    <section className="flex flex-col gap-4" aria-labelledby="account-heading">
      <h2 id="account-heading" className="text-lg font-medium">
        Account
      </h2>
      <dl className="grid max-w-md grid-cols-[8rem_1fr] gap-y-3 text-sm">
        <dt className="text-muted-foreground">Name</dt>
        <dd>{user.name}</dd>
        <dt className="text-muted-foreground">Email</dt>
        <dd className="break-all">{user.email}</dd>
        <dt className="text-muted-foreground">Signed in with</dt>
        <dd>{methods}</dd>
      </dl>
    </section>
  );
}
