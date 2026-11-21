import { describe, expect, it } from "vitest";

import type { InstalledFlow } from "@/lib/api/models";
import { planConnections } from "@/lib/graph/transfer";

import {
  findInstalledFlow,
  flowAsImport,
  flowAsTemplate,
  isMarketplaceTemplate,
  MARKETPLACE_CATEGORY,
} from "./marketplace-flows";

const SLOT = "5b1d7c2e-3a4f-4e6a-9c1b-0d2e8f4a6b01";

const flow: InstalledFlow = {
  id: "slack_alert",
  name: "Alert Slack",
  description: "Posts a message.",
  icon: "plug",
  version: "1.0.0",
  inputs: ["channel"],
  outputs: ["status"],
  connections: { [SLOT]: { type: "slack", name: "Slack" } },
  draft: {
    schema_version: 1,
    variables: [],
    nodes: [
      { id: "start", type: "start", name: "Start", position: { x: 0, y: 0 }, data: { inputs: [] } },
      {
        id: "post",
        type: "http_request",
        name: "Post",
        position: { x: 1, y: 0 },
        data: { connection_id: SLOT },
      },
      { id: "end", type: "end", name: "End", position: { x: 2, y: 0 }, data: { outputs: [] } },
    ],
    edges: [],
  },
};

describe("flowAsTemplate", () => {
  it("lists an installed flow under the Marketplace category with its own id space", () => {
    const template = flowAsTemplate(flow);
    expect(template).toMatchObject({
      id: "marketplace:slack_alert",
      title: "Alert Slack",
      category: MARKETPLACE_CATEGORY,
      inputs: ["channel"],
      outputs: ["status"],
      node_types: ["end", "http_request", "start"],
    });
    expect(isMarketplaceTemplate(template.id)).toBe(true);
    expect(isMarketplaceTemplate("loan-eligibility")).toBe(false);
  });

  it("finds the flow behind a picked row", () => {
    expect(findInstalledFlow([flow], "marketplace:slack_alert")).toBe(flow);
    expect(findInstalledFlow([flow], "slack_alert")).toBeUndefined();
  });
});

describe("flowAsImport", () => {
  it("asks for a connection to be matched for each slot", () => {
    const parsed = flowAsImport(flow, "My alert");
    expect(parsed?.name).toBe("My alert");
    const needs = planConnections(parsed!.graph, parsed!.connections, [
      { id: "mine", name: "Slack", typeId: "slack" },
    ]);
    expect(needs).toEqual([
      { fileId: SLOT, name: "Slack", type: "slack", nodes: 1, suggestion: "mine" },
    ]);
  });

  it("is null for a draft that is not a graph", () => {
    expect(flowAsImport({ ...flow, draft: {} }, "x")).toBeNull();
  });
});
