import type { ReactNode } from "react";

import { Logo } from "@/components/logo";

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
      <h1>
        <Logo className="text-3xl" markClassName="size-10" />
      </h1>
      <section
        aria-labelledby="auth-heading"
        className="flex w-full max-w-sm flex-col gap-5 rounded-lg border p-6"
      >
        <h2 id="auth-heading" className="text-lg font-medium">
          {title}
        </h2>
        {children}
      </section>
    </main>
  );
}
