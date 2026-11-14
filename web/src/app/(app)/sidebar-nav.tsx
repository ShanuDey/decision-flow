"use client";

import { GitBranch, LayoutDashboard, type LucideIcon, Play, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface Item {
  href: string;
  label: string;
  icon: LucideIcon;
  soon?: boolean;
}

const ITEMS: Item[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/flows", label: "Flows", icon: GitBranch },
  { href: "/runs", label: "Runs", icon: Play, soon: true },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ROW = "flex h-11 items-center gap-2.5 rounded-lg px-3 text-sm font-medium";

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {ITEMS.map(({ href, label, icon: Icon, soon }) =>
        soon ? (
          <span key={href} aria-disabled="true" className={cn(ROW, "text-muted-foreground/60")}>
            <Icon className="size-4" aria-hidden />
            {label}
            <span className="ml-auto text-xs font-normal">Soon</span>
          </span>
        ) : (
          <Link
            key={href}
            href={href}
            aria-current={pathname.startsWith(href) ? "page" : undefined}
            className={cn(
              ROW,
              "text-foreground hover:bg-muted",
              pathname.startsWith(href) && "bg-muted",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        ),
      )}
    </nav>
  );
}
