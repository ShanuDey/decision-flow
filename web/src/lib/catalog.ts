export interface CatalogItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  docsUrl: string;
  group: string;
  tags: string[];
}

export function filterItems(items: CatalogItem[], query: string): CatalogItem[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return items;
  return items.filter((item) =>
    `${item.name} ${item.description} ${item.tags.join(" ")}`.toLowerCase().includes(needle),
  );
}

export function groupItems(items: CatalogItem[], order: string[]): { label: string; items: CatalogItem[] }[] {
  return order
    .map((label) => ({ label, items: items.filter((item) => item.group === label) }))
    .filter((section) => section.items.length > 0);
}
