# Templates

Node settings can embed values with `{{ ... }}`.

- `{{ input.amount }}`: a [Start](../nodes/start.md) input
- `{{ vars.total }}`: a [variable](variables.md)

A value that is only one reference keeps its type. Inside other text it becomes a string (arrays and objects as JSON).

Undeclared names fail validation; reading a value that is not set fails the run.
