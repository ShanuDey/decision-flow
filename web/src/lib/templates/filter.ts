import type { Template } from "@/lib/api/models";

export const ALL_CATEGORIES = "all";

export function categoriesOf(items: Template[]): string[] {
  return [...new Set(items.map((t) => t.category))].sort();
}

export function filterTemplates(items: Template[], query: string, category: string): Template[] {
  const needle = query.trim().toLowerCase();
  return items.filter((t) => {
    if (category !== ALL_CATEGORIES && t.category !== category) return false;
    return (
      !needle || `${t.title} ${t.summary} ${t.description} ${t.category}`.toLowerCase().includes(needle)
    );
  });
}

export function groupByCategory(items: Template[]): { category: string; items: Template[] }[] {
  return categoriesOf(items)
    .map((category) => ({ category, items: items.filter((t) => t.category === category) }))
    .filter((g) => g.items.length > 0);
}

export function flatTemplates(groups: { items: Template[] }[]): Template[] {
  return groups.flatMap((g) => g.items);
}
