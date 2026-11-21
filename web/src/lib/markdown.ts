const LINK_PROTOCOLS = new Set(["https:", "http:", "mailto:"]);

// A link from a file we do not write: only plain web and mail links, never javascript: or data:.
export function safeHref(href: string): string | undefined {
  const trimmed = href.trim();
  try {
    return LINK_PROTOCOLS.has(new URL(trimmed).protocol) ? trimmed : undefined;
  } catch {
    return undefined;
  }
}
