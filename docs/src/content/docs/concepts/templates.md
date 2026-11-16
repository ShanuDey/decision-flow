---
title: "Templates"
---

Node settings can embed values with `{{ ... }}`.

- `{{ input.amount }}`: a [Start](../nodes/start) input
- `{{ vars.total }}`: a [variable](variables)
- `{{ nodes.call.output.body.score }}`: the output of a node that runs earlier, for example an [HTTP Request](../nodes/http-request)
- `{{ secrets.API_KEY }}`: a [secret](../secrets), only in fields that accept one

A value that is only one reference keeps its type. Inside other text it becomes a string (arrays and objects as JSON).

Undeclared names fail validation; reading a value that is not set fails the run.
