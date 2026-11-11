import type { Metadata } from "next";

import { ThemePicker } from "./theme-picker";

export const metadata: Metadata = { title: "Appearance · Decision Flow" };

export default function AppearancePage() {
  return (
    <section className="flex flex-col gap-4" aria-labelledby="theme-heading">
      <div>
        <h2 id="theme-heading" className="text-lg font-medium">
          Theme
        </h2>
        <p className="text-sm text-muted-foreground">
          Choose how Decision Flow looks. System follows your device setting.
        </p>
      </div>
      <ThemePicker />
    </section>
  );
}
