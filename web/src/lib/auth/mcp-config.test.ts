import { describe, expect, it } from "vitest";

import { createKeyBody } from "./key-request";
import { AGENT_KEY, claudeCodeCommand, jsonConfig, mcpUrl } from "./mcp-config";
import { ACTIONS } from "./scopes";

const KEY = `df_live_${"c".repeat(64)}`;

describe("AGENT_KEY", () => {
  it("is a body the key route accepts", () => {
    expect(createKeyBody.safeParse(AGENT_KEY).success).toBe(true);
  });

  it("holds every scope and expires", () => {
    expect([...AGENT_KEY.actions]).toEqual([...ACTIONS]);
    expect(AGENT_KEY.expiresInDays).toBe(30);
  });
});

describe("mcpUrl", () => {
  it("adds the path to the site origin", () => {
    expect(mcpUrl("https://flows.example.com")).toBe("https://flows.example.com/mcp");
    expect(mcpUrl("http://localhost:3000")).toBe("http://localhost:3000/mcp");
  });

  it("does not double a trailing slash", () => {
    expect(mcpUrl("https://flows.example.com/")).toBe("https://flows.example.com/mcp");
  });
});

describe("claudeCodeCommand", () => {
  it("adds an HTTP server with the key as a bearer header", () => {
    expect(claudeCodeCommand("https://flows.example.com/mcp", KEY)).toBe(
      `claude mcp add --transport http decision-flow https://flows.example.com/mcp --header "Authorization: Bearer ${KEY}"`,
    );
  });
});

describe("jsonConfig", () => {
  it("is valid JSON with the URL and the bearer header", () => {
    const parsed = JSON.parse(jsonConfig("https://flows.example.com/mcp", KEY));
    expect(parsed).toEqual({
      mcpServers: {
        "decision-flow": {
          url: "https://flows.example.com/mcp",
          headers: { Authorization: `Bearer ${KEY}` },
        },
      },
    });
  });
});
