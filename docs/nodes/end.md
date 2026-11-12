# End

Finishes the run and returns the output. A flow needs at least one; all End nodes must declare the same outputs (otherwise `end_outputs_differ`).

| Setting | Meaning |
|---|---|
| `outputs` | List of `name`, `type` and `value` ([template](../concepts/templates.md)) |

```json
{ "name": "total", "type": "number", "value": "{{ vars.total }}" }
```
