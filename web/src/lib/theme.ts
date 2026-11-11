export const THEMES = ["light", "dark", "system"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_LABELS: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export function parseTheme(value: unknown): Theme {
  return THEMES.find((t) => t === value) ?? "system";
}
