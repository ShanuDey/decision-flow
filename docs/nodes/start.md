# Start

Entry point. Every flow has exactly one. It declares the flow's inputs.

| Setting | Meaning |
|---|---|
| `inputs` | List of `name`, `type`, `required` (default true) and optional `default` |

Runs fail if an input is missing, has the wrong type, or is an undeclared field.
