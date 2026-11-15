---
title: "Getting started"
---

This walks you through running Decision Flow locally and building your first flow.

## Run it locally

You need Docker, [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/).

```
make start
```

This starts Postgres in Docker, the API on port 8000 and the web app on port 3000, both with hot reload. It also runs `make auth-setup`, which adds a local admin account to your untracked `.env` (see [Authentication](auth)).

Open `http://localhost:3000` and sign in with the admin email and password from `.env`.

## Create your first flow

1. Choose **New flow**.
2. Pick a [template](flow-templates) such as *Loan eligibility*, or start from a blank flow. Name it. You get your own draft copy.
3. On the canvas, select the [Start](nodes/start) node to see the inputs the flow expects.
4. Select the [Condition](nodes/condition) node to see its [expression](concepts/expressions), for example `input.income >= 30000 && input.credit_score >= 600`.
5. Check that each path ends at an [End](nodes/end) node that declares the outputs.

## Run it and read the trace

1. Run the flow from the editor and fill in the inputs.
2. Open the **Trace** tab under the editor. Each row is one node, in the order they ran.
3. Click the Condition row. Its output shows the expression and its result, which tells you why the run took that branch.

See [Traces](traces) for everything the view offers.

## Next steps

- Learn how values move through a flow: [Variables](concepts/variables), [Templates](concepts/templates) and [Expressions](concepts/expressions).
- Call your flows from code: see the API reference, or [connect an AI agent](mcp).
- Deploying for others? Read [Configuration](configuration), [Authentication](auth) and [Limits](limits).
