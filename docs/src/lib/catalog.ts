import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

export type Kind = "connection-type" | "node-template";
export type Source = "builtin" | "marketplace";

export const KINDS: Record<Kind, { dir: string; label: string; plural: string }> = {
  "connection-type": { dir: "connection-types", label: "Connection", plural: "Connection types" },
  "node-template": { dir: "node-templates", label: "Template", plural: "Request templates" },
};

export interface CatalogItem {
  kind: Kind;
  source: Source;
  id: string;
  name: string;
  description: string;
  icon: string;
  version: string;
  tags: string[];
  docsUrl: string;
  body: Record<string, any>;
  // Content collection id of the item's README.md, when it has one.
  readme: string | null;
}

const BUILT_IN_DATA: Record<Kind, string> = {
  "connection-type": "api/app/connections/data",
  "node-template": "api/app/node_templates/data",
};
const ID = /^[a-z][a-z0-9_]*$/;
const VERSION = /^\d+\.\d+\.\d+$/;

// The docs build runs with the docs/ folder as the working directory.
const repo = resolve(process.cwd(), "..");

function load(file: string, kind: Kind): Record<string, any> {
  let body: any;
  try {
    body = JSON.parse(readFileSync(file, "utf8"));
  } catch (error) {
    throw new Error(`${file}: ${(error as Error).message}`);
  }
  const problems: string[] = [];
  if (typeof body !== "object" || body === null || Array.isArray(body)) problems.push("not an object");
  else {
    for (const key of ["id", "name", "description"]) {
      if (typeof body[key] !== "string" || !body[key]) problems.push(`missing ${key}`);
    }
    if (typeof body.id === "string" && !ID.test(body.id)) problems.push("bad id");
    if (typeof body.version !== "string" || !VERSION.test(body.version)) problems.push("missing or bad version");
    if (kind === "connection-type" && !(Array.isArray(body.fields) && body.auth?.kind)) {
      problems.push("a connection type needs fields and auth");
    }
    if (kind === "node-template" && (typeof body.node_type !== "string" || typeof body.data !== "object")) {
      problems.push("a template needs node_type and data");
    }
  }
  if (problems.length) throw new Error(`${file}: ${problems.join(", ")}`);
  return body;
}

// The API refuses non-https links in catalog files; the docs build applies the same rule.
function httpsLink(value: unknown): string {
  try {
    return typeof value === "string" && new URL(value).protocol === "https:" ? value : "";
  } catch {
    return "";
  }
}

function item(body: Record<string, any>, kind: Kind, source: Source, readme: string | null): CatalogItem {
  return {
    kind,
    source,
    id: body.id,
    name: body.name,
    description: body.description,
    icon: typeof body.icon === "string" ? body.icon : "plug",
    version: body.version,
    tags: Array.isArray(body.tags) ? body.tags.map(String) : [],
    docsUrl: httpsLink(body.docs_url),
    body,
    readme,
  };
}

function newer(a: string, b: string): boolean {
  const [x, y] = [a, b].map((v) => v.split(".").map(Number));
  const at = x.findIndex((n, i) => n !== y[i]);
  return at >= 0 && x[at] > y[at];
}

function builtIn(kind: Kind): CatalogItem[] {
  const dir = join(repo, BUILT_IN_DATA[kind]);
  if (!existsSync(dir)) throw new Error(`${dir}: built-in data folder not found`);
  return readdirSync(dir)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => item(load(join(dir, name), kind), kind, "builtin", null));
}

function marketplace(kind: Kind): CatalogItem[] {
  const dir = join(repo, "marketplace", "catalog", KINDS[kind].dir);
  if (!existsSync(dir)) throw new Error(`${dir}: marketplace folder not found`);
  const found: CatalogItem[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) throw new Error(`${join(dir, entry.name)}: only <id>/ folders belong here`);
    const folder = join(dir, entry.name);
    let best: Record<string, any> | null = null;
    for (const name of readdirSync(folder).filter((n) => n.endsWith(".json"))) {
      const body = load(join(folder, name), kind);
      if (body.id !== entry.name || `${body.version}.json` !== name) {
        throw new Error(`${join(folder, name)}: the path must be <id>/<version>.json`);
      }
      if (!best || newer(body.version, best.version)) best = body;
    }
    if (!best) throw new Error(`${folder}: no version files`);
    const readme = existsSync(join(folder, "README.md")) ? `${KINDS[kind].dir}/${entry.name}/readme` : null;
    found.push(item(best, kind, "marketplace", readme));
  }
  return found.sort((a, b) => a.name.localeCompare(b.name));
}

export function loadCatalog(): CatalogItem[] {
  const all = (Object.keys(KINDS) as Kind[]).flatMap((kind) => [...builtIn(kind), ...marketplace(kind)]);
  const seen = new Set<string>();
  for (const entry of all) {
    const key = `${entry.kind}/${entry.id}`;
    if (seen.has(key)) throw new Error(`duplicate catalog item ${key}`);
    seen.add(key);
  }
  return all;
}

export const itemPath = (entry: CatalogItem) => `catalog/${KINDS[entry.kind].dir}/${entry.id}`;
