export const STORAGE_KEY = "decision-flow:app-url";

export const TARGETS = {
  home: "/",
  marketplace: "/marketplace",
  connections: "/connections",
};

/** An origin the user may be sent to: http or https, so a self-hosted app on a LAN works. Else null. */
export function normalizeAppUrl(input) {
  let url;
  try {
    url = new URL(String(input ?? "").trim());
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;
  return url.origin;
}

export function targetPath(name) {
  return Object.hasOwn(TARGETS, name) ? TARGETS[name] : TARGETS.home;
}

/** Where to send the visitor, or ask for their app URL when none is known. */
export function resolve(target, savedUrl) {
  const origin = normalizeAppUrl(savedUrl);
  if (!origin) return { kind: "ask" };
  return { kind: "go", url: origin + targetPath(target) };
}
