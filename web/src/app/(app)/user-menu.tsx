"use client";

import { ChevronDown, ChevronUp, LogOut, SlidersHorizontal } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { authClient } from "@/lib/auth/client";
import { initials } from "@/lib/auth/format";
import { parseTheme, THEME_LABELS, THEMES } from "@/lib/theme";
import { cn } from "@/lib/utils";

interface Props {
  name: string;
  email: string;
  // "bar" is the compact editor top-bar version; it adds Settings and a theme switch.
  variant?: "sidebar" | "bar";
  settingsHref?: string;
  // Lets the editor ask about unsaved changes before the menu navigates away.
  guard?: (go: () => void) => void;
}

const subscribeNever = () => () => {};

function ThemeSwitch() {
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);
  const current = mounted ? parseTheme(theme) : "";

  return (
    <DropdownMenuGroup>
      <DropdownMenuLabel>Theme</DropdownMenuLabel>
      <DropdownMenuRadioGroup value={current} onValueChange={(v) => setTheme(parseTheme(v))}>
        {THEMES.map((t) => (
          <DropdownMenuRadioItem key={t} value={t} closeOnClick={false}>
            {THEME_LABELS[t]}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </DropdownMenuGroup>
  );
}

export function UserMenu({ name, email, variant = "sidebar", settingsHref, guard }: Props) {
  const router = useRouter();
  const go = (action: () => void) => (guard ? guard(action) : action());
  const bar = variant === "bar";

  async function signOut() {
    await authClient.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className={cn(
          "flex items-center rounded-lg text-sm font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
          bar ? "h-10 gap-1.5 border px-1.5" : "h-11 w-full gap-2.5 px-3 text-left",
        )}
      >
        <span
          aria-hidden
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground"
        >
          {initials(name, email)}
        </span>
        {!bar && <span className="min-w-0 flex-1 truncate">{name}</span>}
        {bar ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronUp className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={bar ? "bottom" : "top"}
        align={bar ? "end" : "start"}
        className={bar ? "w-64" : "w-52"}
      >
        <div className="px-2 py-1.5">
          <p className="truncate text-sm font-medium">{name}</p>
          <p className="truncate text-xs text-muted-foreground">{email}</p>
        </div>
        <DropdownMenuSeparator />
        {bar ? (
          <>
            <ThemeSwitch />
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => go(() => router.push(settingsHref ?? "/settings/appearance"))}
            >
              <SlidersHorizontal aria-hidden /> Settings
            </DropdownMenuItem>
          </>
        ) : (
          <DropdownMenuItem render={<Link href="/settings/account" />}>Account</DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={() => go(() => void signOut())}>
          {bar && <LogOut aria-hidden />} Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
