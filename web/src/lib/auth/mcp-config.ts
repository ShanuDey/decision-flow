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

export function jsonConfig(url: string, key: string): string {
  const server = { url, headers: { Authorization: `Bearer ${key}` } };
  return JSON.stringify({ mcpServers: { [MCP_SERVER_NAME]: server } }, null, 2);
}
