"use client";

import { Radio } from "@base-ui/react/radio";
import { RadioGroup } from "@base-ui/react/radio-group";
import { type LucideIcon, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { parseTheme, THEME_LABELS, THEMES, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const ICONS: Record<Theme, LucideIcon> = { light: Sun, dark: Moon, system: Monitor };

const subscribe = () => () => {};

export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const value = mounted ? parseTheme(theme) : "";

  return (
    <RadioGroup
      aria-label="Theme"
      value={value}
      onValueChange={(v) => setTheme(parseTheme(v))}
      className="grid gap-3 sm:grid-cols-3"
    >
      {THEMES.map((t) => {
        const Icon = ICONS[t];
        return (
          <label
            key={t}
            className={cn(
              "flex h-24 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border text-sm font-medium hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
              value === t && "border-primary bg-muted",
            )}
          >
            <Radio.Root value={t} className="sr-only" />
            <Icon className="size-5" aria-hidden />
            {THEME_LABELS[t]}
          </label>
        );
      })}
    </RadioGroup>
  );
}
