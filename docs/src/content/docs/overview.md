---
title: "Overview"
---

Decision Flow is a visual editor for business decisions. You draw a decision as a flow of nodes, save it, and run it with a set of inputs to get outputs back. Every run records what each node did, so you can see why it went the way it did.

## How it fits together

- **Editor:** a web app where you build and test flows on a canvas.
- **API:** stores flows and runs them. Anything the editor can do, you can do over HTTP (see the API reference) or from an AI agent (see [Connect an AI agent](mcp)).
- **Traces:** each run records every step's input and output (see [Traces](traces)).

## A flow in one minute

A flow starts at a [Start](nodes/start) node, which declares the inputs. [Assign](nodes/assign) nodes set variables, [Condition](nodes/condition) nodes pick a branch, and every path finishes at an [End](nodes/end) node, which declares the outputs.

```
Start ──► Condition ──true──► End (approved)
              │
              └──false──► End (declined)
```

Nodes read values with [expressions](concepts/expressions) and [templates](concepts/templates), using `input` for the run's inputs and `vars` for [variables](concepts/variables).

## Where to go next

- New here? Follow [Getting started](getting-started).
- Want a head start? Begin from a [flow template](flow-templates).
- Running your own deployment? See [Authentication](auth), [Configuration](configuration) and [Limits](limits).
