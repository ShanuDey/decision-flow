import { ACTIONS } from "./scopes";

export const MCP_SERVER_NAME = "decision-flow";

// What "Connect an AI agent" creates: full access, so a first try never hits a missing scope.
export const AGENT_KEY = { name: "AI agent", actions: [...ACTIONS], expiresInDays: 30 } as const;

export const mcpUrl = (origin: string): string => `${origin.replace(/\/+$/, "")}/mcp`;

export function claudeCodeCommand(url: string, key: string): string {
  return `claude mcp add --transport http ${MCP_SERVER_NAME} ${url} --header "Authorization: Bearer ${key}"`;
}

export function jsonConfig(url: string, key: string): string {
  const server = { url, headers: { Authorization: `Bearer ${key}` } };
  return JSON.stringify({ mcpServers: { [MCP_SERVER_NAME]: server } }, null, 2);
}
