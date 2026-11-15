import Link from "next/link";

import { EntryLink } from "@/app/entry-link";
import { Logo } from "@/components/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  return (
    <header className="flex items-center justify-between gap-3 border-b px-5 py-3.5 md:px-8">
      <Link href="/" aria-label="Decision Flow home">
        <Logo />
      </Link>
      <nav aria-label="Main" className="flex items-center gap-4">
        <a href="/docs" className="text-sm text-muted-foreground hover:text-foreground">
          Docs
        </a>
        <EntryLink
          signedOutLabel="Sign in"
          signedInLabel="Dashboard"
          className={cn(buttonVariants(), "h-9 min-w-24")}
        />
      </nav>
    </header>
  );
}
