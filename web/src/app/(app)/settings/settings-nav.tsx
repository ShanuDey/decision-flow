"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/settings/appearance", label: "Appearance" },
  { href: "/settings/account", label: "Account" },
  { href: "/settings/system", label: "System" },
];

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Settings" className="flex shrink-0 flex-row gap-1 md:w-48 md:flex-col">
      {ITEMS.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
          className={cn(
            "flex h-10 items-center rounded-lg px-3 text-sm font-medium hover:bg-muted",
            pathname === href && "bg-muted",
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
