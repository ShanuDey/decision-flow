import type { CreateKeyBody } from "./key-request";
import { ACTIONS, type Action } from "./scopes";

export const MCP_SERVER_NAME = "decision-flow";

export const DEFAULT_AGENT_NAME = "AI agent";

export const DEFAULT_AGENT_EXPIRY = "30";

// Defaults to full access, so a first try never hits a missing scope.
export const agentKey = (
  name: string,
  actions: readonly Action[] = ACTIONS,
  expiresInDays: CreateKeyBody["expiresInDays"] = 30,
): CreateKeyBody => ({ name, actions: [...actions], expiresInDays });

export const mcpUrl = (origin: string): string => `${origin.replace(/\/+$/, "")}/mcp`;

export function claudeCodeCommand(url: string, key: string): string {
  return `claude mcp add --transport http ${MCP_SERVER_NAME} ${url} --header "Authorization: Bearer ${key}"`;
}

export function agentPrompt(url: string, key: string): string {
  return [
    `Install the Decision Flow MCP server (name: ${MCP_SERVER_NAME}) in the client you are running in.`,
    `It is a remote streamable HTTP server at ${url}, authenticated with the header "Authorization: Bearer ${key}".`,
    `Use this client's own way to add one (Claude Code: ${claudeCodeCommand(url, key)}).`,
    "Store the key in user-level or local config, never in a file that gets committed. If a restart is needed, tell me.",
    "Then call list_flows to check it works, retrying once after a minute if it fails.",
    "Report success or the error (401 means a bad or expired key). Never print the key back.",
  ].join("\n");
}

export function jsonConfig(url: string, key: string): string {
  const server = { url, headers: { Authorization: `Bearer ${key}` } };
  return JSON.stringify({ mcpServers: { [MCP_SERVER_NAME]: server } }, null, 2);
}
