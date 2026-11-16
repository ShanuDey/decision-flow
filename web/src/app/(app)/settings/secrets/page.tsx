import { CircleX } from "lucide-react";
import type { Metadata } from "next";

import { RetryButton } from "@/components/retry-button";
import { listSecrets } from "@/lib/api/client";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";

import { type SecretRow, SecretsPanel } from "./secrets-panel";

export const metadata: Metadata = { title: "Secrets · Decision Flow" };
export const maxDuration = 60;

export default async function SecretsPage() {
  const result = await call(listSecrets(await serverApiInit()));

  if (!result.ok) {
    return (
      <p role="alert" className="flex items-center gap-2 rounded-xl border p-4 text-sm">
        <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
        {isUnreachable(result.error)
          ? UNREACHABLE_MESSAGE
          : `Could not load secrets: ${errorText(result.error)}`}
        <RetryButton />
      </p>
    );
  }

  const rows: SecretRow[] = result.data.items.map(({ name, created_at, updated_at }) => ({
    name,
    createdAt: created_at,
    updatedAt: updated_at,
  }));

  return <SecretsPanel rows={rows} />;
}
