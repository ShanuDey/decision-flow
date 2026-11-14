"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

export function BackToFlow() {
  const from = useSearchParams().get("from");
  if (!from || !/^\/flows\/[\w-]+$/.test(from)) return null;
  return (
    <Link
      href={from}
      className="flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden /> Back to flow
    </Link>
  );
}
