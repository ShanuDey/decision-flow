# Assign

Sets [variables](../concepts/variables.md).

| Setting | Meaning |
|---|---|
| `assignments` | List of `variable` and `value` ([template](../concepts/templates.md)) |

Assignments run in order, so later ones see earlier results. The variable must be declared and the value must match its type.

```json
{ "variable": "total", "value": "{{ input.amount }}" },
{ "variable": "label", "value": "Total {{ vars.total }}" }
```
