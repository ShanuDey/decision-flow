"use client";

import {
  BookOpen,
  Bot,
  ExternalLink,
  GitBranch,
  LayoutDashboard,
  type LucideIcon,
  Play,
  Plug,
  Settings,
  Store,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface Item {
  href: string;
  label: string;
  icon: LucideIcon;
}

const ITEMS: Item[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/flows", label: "Flows", icon: GitBranch },
  { href: "/runs", label: "Runs", icon: Play },
  { href: "/connections", label: "Connections", icon: Plug },
  { href: "/marketplace", label: "Marketplace", icon: Store },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ROW = "flex h-11 items-center gap-2.5 rounded-lg px-3 text-sm font-medium";

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {ITEMS.map(({ href, label, icon: Icon }) => (
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
      ))}
      <a
        href="/docs"
        target="_blank"
        rel="noreferrer"
        className={cn(ROW, "text-foreground hover:bg-muted")}
      >
        <BookOpen className="size-4" aria-hidden />
        Docs
        <ExternalLink className="ml-auto size-3.5 text-muted-foreground" aria-hidden />
      </a>
    </nav>
  );
}
