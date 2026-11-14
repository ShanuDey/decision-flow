import { Check, Code2, Heart, LineChart, type LucideIcon, MousePointerClick, Star } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";
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

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M12 .5a11.5 11.5 0 0 0-3.63 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a10.9 10.9 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.7 5.4-5.27 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export default function Home() {
  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="flex items-center justify-between gap-3 border-b px-5 py-3.5 md:px-8">
        <Link href="/" aria-label="Decision Flow home">
          <Logo />
        </Link>
        <EntryLink
          signedOutLabel="Sign in"
          signedInLabel="Dashboard"
          className={cn(buttonVariants(), "h-9 min-w-24")}
        />
      </header>

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

      <footer className="flex items-center justify-between gap-3 border-t px-5 py-4 text-sm text-muted-foreground md:px-8">
        <span>Decision Flow</span>
        <nav aria-label="Project links" className="flex items-center gap-4">
          <a
            href="https://github.com/ShanuDey/decision-flow"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Star Decision Flow on GitHub"
            title="Star on GitHub"
            className="hover:text-foreground"
          >
            <Star className="size-5" aria-hidden />
          </a>
          <a
            href="https://github.com/sponsors/ShanuDey"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Sponsor on GitHub"
            title="Sponsor"
            className="hover:text-foreground"
          >
            <Heart className="size-5" aria-hidden />
          </a>
          <a
            href="https://github.com/ShanuDey/decision-flow"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Decision Flow on GitHub"
            title="GitHub"
            className="hover:text-foreground"
          >
            <GithubIcon className="size-5" />
          </a>
        </nav>
      </footer>
    </div>
  );
}
