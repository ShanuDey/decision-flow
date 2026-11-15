import { Check, Code2, LineChart, type LucideIcon, MousePointerClick } from "lucide-react";
import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { buttonVariants } from "@/components/ui/button";
import { WarmUp } from "@/components/warm-up";
import { cn } from "@/lib/utils";

import { EntryLink } from "./entry-link";
import { LandingGraph } from "./landing-graph";

export const metadata: Metadata = {
  title: "Decision Flow",
  description:
    "Draw decision logic in a visual editor. Decision Flow compiles it to LangGraph and traces every run in MLflow.",
};

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: MousePointerClick,
    title: "Visual editor",
    body: "Drag nodes, connect branches, and edit expressions with instant evaluation.",
  },
  {
    icon: Check,
    title: "Validated before it runs",
    body: "Cycles, dangling edges, and bad expressions are caught while you edit.",
  },
  {
    icon: Code2,
    title: "Compiled to LangGraph",
    body: "Your graph JSON becomes an executable LangGraph, with no glue code to maintain.",
  },
  {
    icon: LineChart,
    title: "Traced in MLflow",
    body: "Every run records its path and values, so you can see why a decision went the way it did.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <WarmUp />
      <SiteHeader />

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-5 py-12 md:px-8 md:py-16">
        <section className="grid items-center gap-10 md:grid-cols-2">
          <div className="flex flex-col gap-5">
            <h1 className="text-4xl font-semibold tracking-tight text-balance md:text-5xl">
              Draw your decision logic. Run it as code.
            </h1>
            <p className="max-w-[46ch] text-base text-muted-foreground">
              Build rules and branching in a visual editor. Decision Flow validates the graph,
              compiles it to LangGraph, and traces every run in MLflow.
            </p>
            <div className="flex flex-wrap gap-3">
              <EntryLink
                signedOutLabel="Get started"
                signedInLabel="Go to dashboard"
                className={cn(buttonVariants({ size: "lg" }), "h-11 min-w-40 px-5")}
              />
            </div>
          </div>
          <div className="min-w-0 overflow-hidden rounded-xl border">
            <LandingGraph />
          </div>
        </section>

        <section aria-label="Features" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex flex-col gap-1.5 rounded-xl border bg-card p-5">
              <span className="mb-2 grid size-8 place-items-center rounded-lg bg-muted">
                <Icon className="size-4" aria-hidden />
              </span>
              <h2 className="text-[15px] font-semibold">{title}</h2>
              <p className="text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
