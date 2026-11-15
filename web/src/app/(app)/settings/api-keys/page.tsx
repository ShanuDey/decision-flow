import type { Metadata } from "next";
import { headers } from "next/headers";

import { actionsOf } from "@/lib/auth/key-request";
import { getAuth } from "@/lib/auth/server";
import { requireSession } from "@/lib/auth/session";

import { ApiKeysPanel, type KeyRow } from "./api-keys-panel";

export const metadata: Metadata = { title: "API keys · Decision Flow" };

const iso = (value: Date | string | null): string | null => (value ? new Date(value).toISOString() : null);

export default async function ApiKeysPage() {
  const requestHeaders = await headers();
  await requireSession();
  const { apiKeys } = await getAuth().api.listApiKeys({ headers: requestHeaders });

  // Explicit fields only: nothing else from the stored key may reach the browser.
  const rows: KeyRow[] = apiKeys
    .map((key) => ({
      id: key.id,
      name: key.name ?? "Untitled",
      start: key.start ?? "",
      actions: actionsOf(key.permissions),
      expiresAt: iso(key.expiresAt),
      lastUsedAt: iso(key.lastRequest),
      createdAt: iso(key.createdAt) ?? "",
    }))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return <ApiKeysPanel rows={rows} />;
}
