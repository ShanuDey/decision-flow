---
title: "Connect an AI agent (MCP)"
---

The web server exposes your flows to AI agents over the Model Context Protocol (MCP). An agent can list and read flows, write and publish them, and run them, using an API key.

## Quick setup

1. Open **Settings → API keys** and choose **Connect an AI agent**.
2. Name the agent (for example `Claude Code on my laptop`). Use one name per agent or machine so you can revoke one without affecting the others.
3. Pick the scopes the agent needs and when the key expires. The defaults are read, write and run access for 30 days.
4. Choose **Create key and show setup**, then copy the command or config shown. The key is shown once.

Revoke the key from the same page at any time. Each agent should have its own key; the name is only a label in the key list.

## Endpoint

```
POST <web-url>/mcp
Authorization: Bearer df_live_...
```

The server is stateless and speaks HTTP only (no SSE stream). After a quiet spell the API may take a few minutes to wake up, so if the first call fails, try again shortly.

## Client setup

### Claude Code

```
claude mcp add --transport http decision-flow https://<web-url>/mcp --header "Authorization: Bearer <key>"
```

To connect a second agent or machine, create another key and run the same command with that key. Use a different server name in place of `decision-flow` if you add more than one to the same client.

### Other clients

Clients that take a server URL and headers use this shape. Check your client's docs for the file name and field names.

```json
{
  "mcpServers": {
    "decision-flow": {
      "url": "https://<web-url>/mcp",
      "headers": { "Authorization": "Bearer <key>" }
    }
  }
}
```

## Tools

| Tool | Needs | What it does |
|---|---|---|
| `list_flows`, `get_flow` | read | List flows and read one, including its draft |
| `get_flow_format` | read | Describe the flow graph format |
| `validate_flow` | read | Check a flow without changing it |
| `list_runs`, `get_run`, `get_run_steps` | read | Inspect runs and their steps |
| `create_flow`, `save_draft`, `publish_flow` | write | Create a flow, replace its draft, publish a version |
| `create_run` | run | Run a flow |

A tool is refused when the key lacks the scope it needs.

## Keys and safety

- Anyone holding the key can read, change and run your flows. Treat it like a password and keep it out of repositories.
- Keys are listed under **Settings → API keys** with their name, scopes and expiry. Revoke one there and its agent loses access at once.
- Give an agent only the scopes it needs, for example read only for an agent that just inspects flows and runs.
- The same keys also work against the HTTP API; see [Authentication](/docs/auth).
