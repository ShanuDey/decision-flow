import type { ReactNode } from "react";
import { Suspense } from "react";

import { BackToFlow } from "./back-to-flow";
import { SettingsNav } from "./settings-nav";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Suspense>
        <BackToFlow />
      </Suspense>
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <div className="flex flex-col gap-6 md:flex-row md:gap-10">
        <SettingsNav />
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
