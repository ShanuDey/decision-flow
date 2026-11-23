import type { ToolAnnotations } from "@modelcontextprotocol/server";

import { type Action, requiredAction } from "../auth/scopes";
import { isSafeSegment } from "../backend-proxy";
import type { OpenApiDoc } from "../docs/public-spec";
import type { JsonSchema } from "./schema";

export const MCP_OPERATIONS = [
  "list_flows",
  "get_flow",
  "get_flow_format",
  "create_flow",
  "save_draft",
  "validate_flow",
  "publish_flow",
  "create_run",
  "list_runs",
  "get_run",
  "get_run_steps",
] as const;

// For a body that is a free-form object the spec cannot describe.
const BODY_NOTES: Record<string, string> = {
  save_draft:
    "The complete flow graph (schema_version, variables, nodes, edges), shaped like `draft` in get_flow.",
};

type Json = Record<string, unknown>;
interface Param {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: Json;
}

export interface ToolRequest {
  method: string;
  path: string;
  search: string;
  headers: Headers;
  body: string | undefined;
}

export interface McpTool {
  name: string;
  title: string;
  description: string;
  action: Action;
  inputSchema: JsonSchema;
  annotations: ToolAnnotations;
  missing(args: Json): string[];
  check(args: Json): string | null;
  request(args: Json): ToolRequest;
}

const argName = (name: string) => name.replace(/-/g, "_");
const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function resolve(node: unknown, spec: OpenApiDoc, depth = 0): unknown {
  if (Array.isArray(node)) return node.map((item) => resolve(item, spec, depth));
  if (!isObject(node)) return node;
  if (typeof node.$ref === "string") {
    const target = /^#\/components\/schemas\/(.+)$/.exec(node.$ref)?.[1];
    const found = target ? spec.components.schemas[target] : undefined;
    return depth > 8 || found === undefined ? {} : resolve(found, spec, depth + 1);
  }
  return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, resolve(value, spec, depth)]));
}

function kindsOf(schema: unknown): string[] {
  if (!isObject(schema)) return [];
  const own = typeof schema.type === "string" ? [schema.type] : [];
  const nested = Array.isArray(schema.anyOf) ? schema.anyOf.flatMap(kindsOf) : [];
  return [...own, ...nested];
}

function isKind(value: unknown, kind: string): boolean {
  switch (kind) {
    case "null":
      return value === null;
    case "string":
      return typeof value === "string";
    case "integer":
      return Number.isInteger(value);
    case "number":
      return typeof value === "number";
    case "boolean":
      return typeof value === "boolean";
    case "array":
      return Array.isArray(value);
    case "object":
      return isObject(value);
    default:
      return true;
  }
}

const isScalar = (value: unknown): boolean => ["string", "number", "boolean"].includes(typeof value);

function annotationsFor(method: string, action: Action): ToolAnnotations {
  if (action.endsWith(":read")) return { readOnlyHint: true, openWorldHint: false };
  const overwrites = method === "DELETE" || method === "PUT" || method === "PATCH";
  return { destructiveHint: overwrites, idempotentHint: overwrites, openWorldHint: false };
}

function toolFor(spec: OpenApiDoc, template: string, method: string, op: Json): McpTool {
  const name = String(op.operationId);
  const action = requiredAction(method, template.replace(/\{[^}]+\}/g, "1"));
  if (!action) throw new Error(`${method} ${template} (${name}) is not a gateway route`);

  const params = ((op.parameters as Param[] | undefined) ?? []).filter((p) =>
    ["path", "query", "header"].includes(p.in),
  );
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  const claim = (key: string, schema: unknown, isRequired: boolean) => {
    if (key in properties) throw new Error(`${name}: argument "${key}" is defined twice`);
    properties[key] = schema;
    if (isRequired) required.push(key);
  };

  for (const param of params) {
    const schema = resolve(param.schema ?? {}, spec) as Json;
    claim(argName(param.name), { ...schema, ...(param.description && { description: param.description }) }, !!param.required);
  }

  const bodySpec = (op.requestBody as { required?: boolean; content?: Record<string, { schema?: unknown }> } | undefined)
    ?.content?.["application/json"]?.schema;
  const body = bodySpec === undefined ? null : (resolve(bodySpec, spec) as Json);
  const bodyKeys: string[] = [];
  let wholeBody: string | null = null;
  if (body && isObject(body.properties)) {
    const bodyRequired = Array.isArray(body.required) ? (body.required as string[]) : [];
    for (const [key, schema] of Object.entries(body.properties)) {
      claim(key, schema, bodyRequired.includes(key));
      bodyKeys.push(key);
    }
  } else if (body) {
    wholeBody = String(body.title ?? "body").toLowerCase().replace(/\W+/g, "_");
    const note = BODY_NOTES[name];
    claim(wholeBody, { ...body, ...(note && { description: note }) }, true);
  }

  const pathKeys = new Set(params.filter((p) => p.in === "path").map((p) => argName(p.name)));
  const paramKeys = new Set(params.map((p) => argName(p.name)));

  const inputSchema: JsonSchema = { type: "object", properties, required, additionalProperties: false };
  const summary = String(op.summary ?? name);
  const present = (args: Json, key: string) => args[key] !== undefined && args[key] !== null;

  return {
    name,
    title: summary,
    description: String(op.description ?? summary).trim(),
    action,
    inputSchema,
    annotations: annotationsFor(method, action),
    missing: (args) => required.filter((key) => !present(args, key)),
    check(args) {
      for (const key of Object.keys(args)) {
        if (!(key in properties)) return `Unknown argument: ${key}.`;
      }
      for (const [key, value] of Object.entries(args)) {
        if (value === undefined || value === null) continue;
        if (paramKeys.has(key)) {
          const items = Array.isArray(value) && !pathKeys.has(key) ? value : [value];
          if (!items.every(isScalar)) return `Argument ${key} must be a string, number or boolean.`;
          if (pathKeys.has(key) && !isSafeSegment(String(value))) return `Argument ${key} is not a valid id.`;
          continue;
        }
        const kinds = kindsOf(properties[key]);
        if (kinds.length > 0 && !kinds.some((kind) => isKind(value, kind))) {
          return `Argument ${key} must be of type ${kinds.join(" or ")}.`;
        }
      }
      return null;
    },
    request(args) {
      const path = template.replace(/\{([^}]+)\}/g, (_, key: string) => encodeURIComponent(String(args[argName(key)])));
      const search = new URLSearchParams();
      const headers = new Headers();
      for (const param of params) {
        const value = args[argName(param.name)];
        if (value === undefined || value === null) continue;
        if (param.in === "header") headers.set(param.name, String(value));
        if (param.in === "query") {
          for (const item of Array.isArray(value) ? value : [value]) search.append(param.name, String(item));
        }
      }
      let payload: string | undefined;
      if (wholeBody) payload = JSON.stringify(args[wholeBody]);
      else if (bodyKeys.length > 0) {
        payload = JSON.stringify(Object.fromEntries(bodyKeys.filter((key) => present(args, key)).map((key) => [key, args[key]])));
      }
      if (payload !== undefined) headers.set("content-type", "application/json");
      return { method, path, search: search.size ? `?${search}` : "", headers, body: payload };
    },
  };
}

export function buildTools(spec: OpenApiDoc, include: readonly string[] = MCP_OPERATIONS): McpTool[] {
  const found = new Map<string, McpTool>();
  for (const [template, item] of Object.entries(spec.paths)) {
    for (const [verb, op] of Object.entries(item)) {
      if (!include.includes(String(op.operationId))) continue;
      const tool = toolFor(spec, template, verb.toUpperCase(), op as Json);
      found.set(tool.name, tool);
    }
  }
  const unknown = include.filter((name) => !found.has(name));
  if (unknown.length > 0) throw new Error(`Not in the public spec: ${unknown.join(", ")}`);
  return include.map((name) => found.get(name)!);
}
