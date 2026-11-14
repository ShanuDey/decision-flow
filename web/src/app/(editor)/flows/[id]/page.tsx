import { CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RetryButton } from "@/components/retry-button";
import { buttonVariants } from "@/components/ui/button";
import { serverApiInit } from "@/lib/auth/session";
import { call, errorText, isUnreachable, UNREACHABLE_MESSAGE } from "@/lib/call";
import { getFlow } from "@/lib/api/client";
import { parseDraft } from "@/lib/graph/convert";

import { EditorLoader } from "./editor-loader";

export const metadata: Metadata = { title: "Editor · Decision Flow" };
export const maxDuration = 60;

export default async function EditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await call(getFlow(id, await serverApiInit()));

  if (!result.ok) {
    if (result.error.status === 404 || result.error.status === 422) notFound();
    const message = isUnreachable(result.error)
      ? UNREACHABLE_MESSAGE
      : `Could not load the flow: ${errorText(result.error)}`;
    return <Problem message={message} retry />;
  }
  const graph = parseDraft(result.data.draft);
  if (!graph) {
    return <Problem message="This flow's draft is not a graph the editor understands (unknown schema version)." />;
  }

  return (
    <EditorLoader
      key={result.data.id}
      id={result.data.id}
      name={result.data.name}
      draftVersion={result.data.draft_version}
      graph={graph}
    />
  );
}

function Problem({ message, retry = false }: { message: string; retry?: boolean }) {
  return (
    <main className="mx-auto flex max-w-lg flex-1 flex-col items-start justify-center gap-4 p-8">
      <p role="alert" className="flex items-start gap-2 text-sm">
        <CircleX className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" aria-hidden />
        {message}
      </p>
      <div className="flex gap-2">
        {retry && <RetryButton />}
        <Link href="/flows" className={buttonVariants({ variant: "outline" })}>
          Back to flows
        </Link>
      </div>
    </main>
  );
}
