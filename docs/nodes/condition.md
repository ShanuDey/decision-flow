# Condition

Sends the run down one of two branches.

| Setting | Meaning |
|---|---|
| `expression` | An [expression](../concepts/expressions.md) that gives `true` or `false` |

A Condition has two outgoing edges: one from its `true` handle and one from its `false` handle. Each handle takes exactly one edge. Both branches may lead to the same node, such as End.

The node's recorded output is the `expression` and its `result`. Later nodes can read it as `nodes.<id>.output.result`.

```json
{ "expression": "input.income >= 30000 && input.credit_score >= 600" }
```

Validation rejects an expression that does not compile, that is plainly not true/false, or that reads something undeclared or from a node that does not run before this one. If the result is not a boolean when the flow runs, or a value it reads is missing, the run fails at this node.

See [`examples/flows/condition.json`](../../examples/flows/condition.json).
