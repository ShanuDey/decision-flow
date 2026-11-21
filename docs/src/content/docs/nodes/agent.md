---
title: "Agent"
---

Gives a chat model a task and a set of your published flows as tools. The model decides which flow to run, with which inputs, reads the result, and repeats until it can answer. Use it when the steps are not known in advance. When they are, a plain graph of nodes is cheaper and easier to predict.

It works with any provider that has an OpenAI-style API and supports tool calls, through an OpenAI-compatible [connection](../connections), like the [Prompt](prompt) node.

| Setting | Meaning |
|---|---|
| `connection_id` | The connection to use. It must be an OpenAI-compatible connection |
| `prompt` | The task, as a [template](../concepts/templates) |
| `instructions` | Optional standing instructions, also a template |
| `tools` | The flows the model may run. Each has a `flow_id`, a `name` and a `description` |
| `model` | Optional template for the model name. Empty uses the connection's default model |
| `max_iterations` | How many times the model may be asked. Default 8, at most 50 |
| `max_total_tokens` | Optional. Stops the agent once the model calls have used this many tokens |
| `max_seconds` | Optional. Total time for the whole agent. Default 120 |
| `temperature`, `max_tokens`, `timeout_seconds` | Optional. Options you leave empty are not sent. `timeout_seconds` applies to each model call |

## Tools

The `name` and `description` are what the model sees, so say what the flow does and when to use it. A flow's own name is not shown. The flow's [Start](start) inputs become the tool's arguments, and its [End](end) outputs come back to the model as the result. The flow runs at its latest published version.

A tool name uses 1 to 64 letters, digits, `_` or `-`, and each tool in a node needs its own name.

```json
{
  "connection_id": "5f0c1a3e-8d2b-4c7e-9a41-2b6f7d8e9c10",
  "prompt": "Find the order status for {{ input.order_id }} and say if it is late",
  "tools": [
    {
      "flow_id": "0a6c2f7e-4b1d-4e0a-8c55-3d1e9f2a7b64",
      "name": "lookup_order",
      "description": "Returns the status and ship date of an order. Needs the order id."
    }
  ]
}
```

If a tool fails, or the model sends inputs the flow rejects, the model is told what went wrong and can try again. The run does not fail. The tool's nodes show in the trace under the agent node.

A flow cannot reach itself through its tools, directly or through other flows, and flows can be nested only as deep as your workspace limit allows.

## Output

| Field | Meaning |
|---|---|
| `text` | The final answer |
| `steps` | Each tool the model ran: `name`, `arguments`, `result` and `is_error` |
| `iterations` | How many times the model was asked |
| `usage` | Tokens used across all model calls |
| `model` | The model that answered |

Later nodes read these as `nodes.<id>.output.<field>`.

## When it stops

The run fails at this node when the agent reaches `max_iterations`, `max_total_tokens` or `max_seconds` before it gives an answer, or when the provider returns an error, as for the [Prompt](prompt) node. Tools with side effects may already have run, so set the limits with that in mind.
