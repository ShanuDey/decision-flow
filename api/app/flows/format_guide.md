# Writing a flow

A flow is a JSON graph with four parts: `schema_version` (always `1`), `variables`, `nodes` and `edges`. You save the whole graph as the flow's draft, validate it, publish it, then run it.

## Nodes

Every node has an `id` (unique in the flow), a `type`, an optional `name` (unique, defaults to the type), an optional `position` (`{"x": 0, "y": 0}`) and `data` with the settings for its type.

- `start`: exactly one. `data.inputs` lists the flow's inputs, each `{ "name", "type", "required" (default true), "default" (optional) }`. A run fails on a missing, mistyped or undeclared input.
- `assign`: `data.assignments` is a list of `{ "variable", "value" }`, run in order. The variable must be declared in `variables` and the value must match its type.
- `condition`: `data.expression` gives true or false. It needs two outgoing edges, one with `sourceHandle` `"true"` and one with `"false"`.
- `http_request`: calls an API. `data` has `method` (`GET` default, `POST`, `PUT`, `PATCH`, `DELETE`), `url`, `headers` and `query` (name to template), `body_type` (`none`, `json`, `form` or `text`) with `body`, and optionally `timeout_seconds` and `fail_on_error_status`. Later nodes read the response as `nodes.<id>.output.status`, `.ok`, `.headers` and `.body`. Header, query and body values may use `{{ secrets.NAME }}`; the URL may not.
- `subflow`: runs another published flow in the same workspace. `data.flow_id` is that flow's id and `data.inputs` maps each of its start inputs to a template. It always runs the flow's latest published version, with its own variables. Later nodes read the flow's end outputs as `nodes.<id>.output.<name>`. A flow cannot call itself, directly or through others.
- `end`: at least one. `data.outputs` is a list of `{ "name", "type", "value" }`. Every `end` node declares the same outputs.

## Edges

`{ "id", "source", "target", "sourceHandle" }`, where source and target are node ids. `sourceHandle` is `null` except on the two edges leaving a `condition`.

## Types, variables and values

Types are `string`, `number`, `boolean`, `object`, `array` and `enum` (an enum also needs a `values` list). Types are strict: `"5"` is not a number.

Declare variables at the top level: `{ "name", "type", "initial" (optional) }`.

Assign and end values are templates. `{{ input.amount }}` reads a start input, `{{ vars.total }}` reads a variable and `{{ nodes.<id>.output.<key> }}` reads the output of a node that runs earlier. A value that is one reference keeps its type; inside other text it becomes a string.

Condition expressions use CEL, for example `input.income >= 30000 && vars.tier == "gold"`. They can read `input.<name>`, `vars.<name>` and `nodes.<id>.output.<key>` from a node that runs earlier. At most 2000 characters.

## Working order

1. Start from the closest example in this answer.
2. `create_flow`, then `get_flow` to read its `draft_version`.
3. `save_draft` with the whole graph and `if_match` set to that version. Saving an invalid graph is allowed.
4. `validate_flow`. Each problem names a `node_id` and a `field`. Fix them and save again with the new `draft_version`.
5. `publish_flow`, then `create_run`. It runs the published version; `test: true` runs the draft instead.
