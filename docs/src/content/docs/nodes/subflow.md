---
title: "Subflow"
---

Runs another published flow in the same workspace as one step, and makes its outputs available to the nodes after it.

| Setting | Meaning |
|---|---|
| `flow_id` | The flow to run. It needs a published version |
| `inputs` | The called flow's input names, each with a [template](../concepts/templates) for its value |

In the editor, pick the flow from the list. The node then shows one row per input the flow declares, with a box for each value. You can use anything the node can read, such as `{{ input.amount }}` or `{{ nodes.score.output.value }}`.

```json
{
  "flow_id": "5f0c1a3e-8d2b-4c7e-9a41-2b6f7d8e9c10",
  "inputs": { "amount": "{{ input.amount }}", "tier": "gold" }
}
```

## Which version runs

Always the flow's latest published version, even when you test the draft of the flow that calls it. Publishing a new version of the called flow changes every flow that calls it.

## Output

The called flow's End outputs are stored at `nodes.<id>.output`. Every End node of a flow declares the same outputs, so the names and types are always known:

`{{ nodes.score.output.risk }}` in an [Assign](assign) or [End](end) value, or `nodes.score.output.risk > 0.8` in a [Condition](condition). A node can read only nodes that run before it.

## What the called flow can see

Only the values you map. It has its own variables and cannot read the caller's input, variables or nodes. [Secrets](../secrets) work inside the called flow as they do anywhere else in the workspace.

## Checks

Validate and publish check each Subflow node:

| Code | Meaning |
|---|---|
| `subflow_not_selected` | No flow is picked |
| `subflow_unavailable` | The flow is missing, or has no published version |
| `unknown_subflow_input` | An input is mapped that the flow does not declare |
| `missing_subflow_input` | A required input has no value |
| `subflow_loop` | The flow calls itself, directly or through other flows |

Reading an output the called flow does not declare is reported as `unknown_reference`. If the called flow changes after you map it, the next Validate shows what no longer fits.

## When it fails

The node fails the run, naming itself. The message says where the called flow failed, for example `the flow failed at 'end': output 'total': expected number`. It also fails when flows are nested more than `MAX_SUBFLOW_DEPTH` levels deep (see [Limits](../limits)).

## Runs and traces

A call is part of the caller's run: it uses the caller's time limit and one run slot, and has no run of its own. In the step history, the called flow's steps are nested under the Subflow step.
