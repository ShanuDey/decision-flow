# Limits

Limits keep one user or workspace from using up a small server. They are environment variables, read once at start. `0` turns a limit off, except `MAX_REQUEST_BYTES`, which always applies.

| Variable | Default | Meaning |
|---|---|---|
| `MAX_REQUEST_BYTES` | `1048576` | Largest request body. A bigger one gets `413` |
| `MAX_CONCURRENT_RUNS` | `10` | Runs in progress at once, across the whole app |
| `MAX_CONCURRENT_RUNS_PER_WORKSPACE` | `0` (off) | Runs in progress at once for one workspace |
| `RUN_TIMEOUT_SECONDS` | `300` | Longest a run may take |

| `LIMIT_NOTICE` | empty | Text added to every limit error, for example how to get more capacity. Up to 300 characters |
| `LIMIT_NOTICE_URL` | empty | A link shown with the notice. Must start with `http://` or `https://` |

A public deployment should set the per-workspace cap and a shorter timeout, for example `MAX_CONCURRENT_RUNS_PER_WORKSPACE=2` and `RUN_TIMEOUT_SECONDS=30`.

## When a limit is reached

- **Too many runs at once:** `POST /flows/{id}/runs` answers `429` with code `run_limit` and a `Retry-After` header (seconds, never more than 5 and never more than the run timeout). `details.scope` is `app` or `workspace`. Nothing is queued: wait and send the request again. A refused request creates no run.
- **Run too long:** the run stops and is recorded as `failed` with the message `Run timed out after N seconds`. The response is `200`, like any other failure inside a flow.

When `LIMIT_NOTICE` is set, every limit error (`429` and `413`) also carries `details.notice`, plus `details.notice_url` if a link is set. The `message` stays the same, so clients keep matching on it. Show the notice as plain text, never as HTML. On a shared demo it can explain why the limit exists, for example: `This is a free demo on shared resources. To get more capacity, self-host it or sponsor the server.`

A request that is rejected for another reason (unknown flow, invalid input) never takes a slot.

## Notes

- Counts are held in memory, so they are per server process. Run one instance, or accept that each instance counts on its own.
- The timeout is checked while a run waits, so it cannot interrupt a node that is busy computing.
- On shutdown the container waits up to 30 seconds for runs in progress. A run still going after that is cut off and leaves no record, because a run is saved when it ends. Keep `RUN_TIMEOUT_SECONDS` below that, and note that a platform may stop the container sooner.
