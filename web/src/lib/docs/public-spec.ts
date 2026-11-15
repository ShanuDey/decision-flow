import { GATEWAY_ROUTES } from "../auth/scopes.ts";

type Operation = { description?: string; responses?: unknown; [key: string]: unknown };

export interface OpenApiDoc {
  openapi: string;
  info: { title: string; version: string; description?: string };
  servers?: { url: string }[];
  paths: Record<string, Record<string, Operation>>;
  components: {
    schemas: Record<string, unknown>;
    securitySchemes: Record<string, unknown>;
  };
}

const TRIGGER = "/flows/{flow_id}/trigger";
const RUNS = "/flows/{flow_id}/runs";
const SCHEMA_REF = /^#\/components\/schemas\/(.+)$/;

const INTRO = [
  "Run and manage decision flows over HTTP.",
  "Create an API key in Settings, then send it as `Authorization: Bearer <key>`.",
  "Each key holds some of the `read`, `write` and `run` scopes; an operation your key lacks returns 403.",
].join(" ");

function collectRefs(node: unknown, into: Set<string>): void {
  if (Array.isArray(node)) {
    node.forEach((item) => collectRefs(item, into));
  } else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      const name = key === "$ref" && typeof value === "string" ? SCHEMA_REF.exec(value)?.[1] : null;
      if (name) into.add(name);
      else collectRefs(value, into);
    }
  }
}

function usedSchemas(paths: OpenApiDoc["paths"], all: Record<string, unknown>) {
  const names = new Set<string>();
  collectRefs(paths, names);
  const queue = [...names];
  for (let name = queue.pop(); name; name = queue.pop()) {
    const found = new Set<string>();
    collectRefs(all[name], found);
    for (const next of found) {
      if (!names.has(next)) {
        names.add(next);
        queue.push(next);
      }
    }
  }
  return Object.fromEntries(
    Object.entries(all)
      .filter(([name]) => names.has(name))
      .sort(([a], [b]) => a.localeCompare(b)),
  );
}

// The API answers 428 without these, though it declares them optional so it can say so itself.
const REQUIRED_PARAMS: Record<string, string[]> = { save_draft: ["if-match"] };

function requireParams(operation: Operation): Operation {
  const names = REQUIRED_PARAMS[String(operation.operationId)];
  if (!names || !Array.isArray(operation.parameters)) return operation;
  const parameters = (operation.parameters as { name: string }[]).map((param) =>
    names.includes(param.name.toLowerCase()) ? { ...param, required: true } : param,
  );
  return { ...operation, parameters };
}

function triggerOperation(runs: Operation): Operation {
  return {
    ...runs,
    summary: "Trigger Flow",
    description:
      "Runs the published version of a flow. Send only `input`; drafts cannot be triggered. " +
      "Same result as creating a run.",
    operationId: "trigger_flow",
    requestBody: {
      required: true,
      content: {
        "application/json": {
          schema: {
            type: "object",
            additionalProperties: false,
            properties: { input: { type: "object", additionalProperties: true, title: "Input" } },
          },
        },
      },
    },
  };
}

export function buildPublicSpec(full: OpenApiDoc): OpenApiDoc {
  const paths: OpenApiDoc["paths"] = {};
  for (const { method, template, action } of GATEWAY_ROUTES) {
    const verb = method.toLowerCase();
    const source =
      template === TRIGGER ? full.paths[RUNS]?.post : full.paths[template]?.[verb];
    if (!source) throw new Error(`${method} ${template} is missing from the API spec`);
    const operation = requireParams(template === TRIGGER ? triggerOperation(source) : { ...source });
    const scope = `Requires the \`${action}\` scope.`;
    operation.description = operation.description ? `${operation.description}\n\n${scope}` : scope;
    (paths[template] ??= {})[verb] = operation;
  }

  return {
    openapi: full.openapi,
    info: { title: "Decision Flow API", version: full.info.version, description: INTRO },
    servers: [{ url: "/api/v1" }],
    paths,
    components: {
      schemas: usedSchemas(paths, full.components.schemas),
      securitySchemes: {
        HTTPBearer: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "API key",
          description: "An API key created in Settings.",
        },
      },
    },
  };
}
