import { describe, expect, it } from "vitest";

import { createKeyBody } from "./key-request";
import { agentKey, claudeCodeCommand, DEFAULT_AGENT_NAME, jsonConfig, mcpUrl } from "./mcp-config";
import { ACTIONS } from "./scopes";

const KEY = `df_live_${"c".repeat(64)}`;

describe("agentKey", () => {
  it("is a body the key route accepts", () => {
    expect(createKeyBody.safeParse(agentKey(DEFAULT_AGENT_NAME)).success).toBe(true);
  });

  it("uses the given name", () => {
    expect(agentKey("Cursor on laptop").name).toBe("Cursor on laptop");
  });

  it("takes custom scopes and expiry", () => {
    const key = agentKey("Reader", ["read"], null);
    expect(key.actions).toEqual(["read"]);
    expect(key.expiresInDays).toBeNull();
    expect(createKeyBody.safeParse(key).success).toBe(true);
  });

  it("holds every scope and expires by default", () => {
    const key = agentKey(DEFAULT_AGENT_NAME);
    expect([...key.actions]).toEqual([...ACTIONS]);
    expect(key.expiresInDays).toBe(30);
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
