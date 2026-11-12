# Variables

Variables hold values while a flow runs. Declare them on the flow, then set them with an [Assign](../nodes/assign.md) node.

| Field | Meaning |
|---|---|
| `name` | Letters, digits and `_`; cannot start with a digit |
| `type` | `string`, `number`, `boolean`, `object`, `array` or `enum` (enum also needs `values`) |
| `initial` | Optional starting value; must match `type` |

Types are strict: `"5"` is not a number.
