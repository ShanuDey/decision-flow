import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { GATEWAY_ROUTES } from "@/lib/auth/scopes";

import { buildPublicSpec, type OpenApiDoc } from "./public-spec";

const full = JSON.parse(
  readFileSync(new URL("../../../../api/openapi.json", import.meta.url), "utf8"),
) as OpenApiDoc;
const spec = buildPublicSpec(full);

describe("buildPublicSpec", () => {
  it("documents exactly the gateway routes", () => {
    const documented = Object.entries(spec.paths).flatMap(([path, ops]) =>
      Object.keys(ops).map((verb) => `${verb.toUpperCase()} ${path}`),
    );
    const allowed = GATEWAY_ROUTES.map((r) => `${r.method} ${r.template}`);
    expect(documented.sort()).toEqual(allowed.sort());
  });

  it("leaves out internal routes", () => {
    for (const path of ["/me", "/config", "/health", "/ready", "/templates", "/expressions/evaluate"]) {
      expect(spec.paths).not.toHaveProperty(path);
    }
  });

  it("names the required scope on every operation", () => {
    for (const { method, template, action } of GATEWAY_ROUTES) {
      const operation = spec.paths[template][method.toLowerCase()];
      expect(operation.description).toContain(`\`${action}\` scope`);
    }
  });

  it("only accepts input when triggering", () => {
    const trigger = spec.paths["/flows/{flow_id}/trigger"].post as {
      requestBody: { content: { "application/json": { schema: unknown } } };
    };
    expect(trigger.requestBody.content["application/json"].schema).toEqual({
      type: "object",
      additionalProperties: false,
      properties: { input: { type: "object", additionalProperties: true, title: "Input" } },
    });
  });

  it("keeps every referenced schema and nothing unused", () => {
    const refs = new Set(
      [...JSON.stringify(spec.paths).matchAll(/#\/components\/schemas\/([\w-]+)/g)].map((m) => m[1]),
    );
    const kept = Object.keys(spec.components.schemas);
    for (const name of refs) expect(kept).toContain(name);
    expect(kept.length).toBeLessThan(Object.keys(full.components.schemas).length);
  });

  it("serves relative to the gateway with bearer auth", () => {
    expect(spec.servers).toEqual([{ url: "/api/v1" }]);
    expect(spec.components.securitySchemes).toHaveProperty("HTTPBearer");
  });
});
