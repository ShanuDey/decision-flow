# Traces

Every run records what each node did. Open it from the **Trace** tab under the editor after a test run, or from a run's page (**Runs**, then click a run).

## What you see

- One row per node, in the order they ran, with the node type, how long it took, and a short result: a Condition shows `true` or `false`, an Assign shows what it set, a failed node shows `error`.
- Click a row to see its **Input** and **Output**. A Condition's output includes the expression that was evaluated and its result, which is the answer to "why did it go this way".
- The input shows what the node itself read (`input` and `vars`). **Show full state** adds the outputs of earlier nodes.
- **Pretty / JSON** switches between labelled fields and raw JSON. **Copy** copies a block.
- **List / Timeline** switches between a plain list and bars showing when each step started and how long it took.
- In the editor, clicking a node's row selects that node on the canvas.

## Good to know

- A trace appears a few seconds after the run ends. Until then the view says it is not ready and checks again by itself.
- If the trace store cannot be reached, the view says so and offers **Retry**. The run itself is not affected.
- A run has no steps if it could not be traced (the trace store was down when it ran) or if its trace was already removed by retention. The view then says no step history is available.
- Inputs and outputs are shown as recorded. Do not put secrets in flow inputs: redaction of recorded values is not in place yet.
- Traces are deleted together with their runs by the [retention](retention.md) timer.
- Nodes added later appear in the trace with their input and output automatically.
