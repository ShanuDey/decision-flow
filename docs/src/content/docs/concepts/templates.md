---
title: "Templates"
---

Node settings can embed values with `{{ ... }}`.

- `{{ input.amount }}`: a [Start](../nodes/start) input
- `{{ vars.total }}`: a [variable](variables)
- `{{ nodes.call.output.body.score }}`: the output of a node that runs earlier, for example an [HTTP Request](../nodes/http-request)
- `{{ secrets.API_KEY }}`: a [secret](../secrets), only in fields that accept one

Anything else inside `{{ }}` is a [CEL](https://cel.dev) expression over `input`, `vars` and `nodes`:

- `{{ input.amount + 1 }}`: arithmetic
- `{{ input.amount > 100 ? "large" : "small" }}`: a condition
- `{{ has(input.coupon) }}`: whether an optional input is set

CEL is strictly typed: an integer and a decimal do not mix, so `input.amount + 0.5` fails unless you write `double(input.amount) + 0.5`. Secrets are plain `{{ secrets.NAME }}` only, not part of an expression. Loops such as `map` and `filter` may nest at most two levels.

A value that is only one expression keeps its type. Inside other text it becomes a string (arrays and objects as JSON).

Undeclared names fail validation; reading a value that is not set fails the run.
