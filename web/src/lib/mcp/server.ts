import { McpServer } from "@modelcontextprotocol/server";

import type { KeyIdentity } from "../auth/api-key";
import publicSpec from "../docs/public-openapi.json";
import type { OpenApiDoc } from "../docs/public-spec";
import { callGateway, type GatewayCall } from "../gateway-v1";
import { failure, resultOf } from "./result";
import { fromJsonSchema } from "./schema";
import { buildTools, type McpTool } from "./tools";

const spec = publicSpec as unknown as OpenApiDoc;

export const INSTRUCTIONS =
  "Flows are decision graphs you can read, edit, publish and run. Start with list_flows. " +
  "To build or change a flow, read get_flow_format first. Then: get_flow (note draft_version), " +
  "save_draft with that value as if_match, validate_flow, publish_flow, then create_run. " +
  "create_run runs the published version; set test to run the draft.";

// Built once: the spec is bundled, so listing tools never needs the API.
export const TOOLS: McpTool[] = buildTools(spec);

export type Gateway = (call: GatewayCall, auth: KeyIdentity) => Promise<Response>;

export function createMcpServer(
  identity: KeyIdentity,
  gateway: Gateway = callGateway,
  tools: McpTool[] = TOOLS,
): McpServer {
  const server = new McpServer(
    { name: "decision-flow", version: spec.info.version },
    { instructions: INSTRUCTIONS },
  );

  for (const tool of tools) {
    server.registerTool(
      tool.name,
      {
        title: tool.title,
        description: tool.description,
        inputSchema: fromJsonSchema(tool.inputSchema),
        annotations: tool.annotations,
      },
      async (args: unknown) => {
        const values = (args ?? {}) as Record<string, unknown>;
        const missing = tool.missing(values);
        if (missing.length > 0) {
          return failure(`Missing required argument${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}.`);
        }
        const invalid = tool.check(values);
        if (invalid) return failure(invalid);
        const { method, path, search, headers, body } = tool.request(values);
        return resultOf(await gateway({ method, path, search, headers, body }, identity));
      },
    );
  }
  return server;
}
