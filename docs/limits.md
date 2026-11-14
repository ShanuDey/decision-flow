# Limits

Limits keep one user or workspace from using up a small server. They are environment variables, read once at start. `0` turns a limit off, except `MAX_REQUEST_BYTES`, which always applies.

| Variable | Default | Meaning |
|---|---|---|
| `MAX_REQUEST_BYTES` | `1048576` | Largest request body. A bigger one gets `413` |
| `MAX_CONCURRENT_RUNS` | `10` | Runs in progress at once, across the whole app |
| `MAX_CONCURRENT_RUNS_PER_WORKSPACE` | `0` (off) | Runs in progress at once for one workspace |
| `RUN_TIMEOUT_SECONDS` | `300` | Longest a run may take |
| `MAX_NODES` | `50` | Most nodes in one flow |
| `MAX_EDGES` | `100` | Most edges in one flow |
| `MAX_FLOWS_PER_USER` | `20` | Most flows one user can create in a workspace. Deleting a flow frees a slot |
| `RATE_LIMIT_IP_PER_MINUTE` | `120` | Requests per minute from one client IP, on every route. Signed-in requests count per visitor IP |
| `RATE_LIMIT_READY_PER_MINUTE` | `6` | Requests per minute from one IP to `/ready` (it queries the database) |
| `RATE_LIMIT_FAILED_AUTH_PER_MINUTE` | `10` | Rejected sign-ins (`401`, `403`) per minute from one IP before that IP is blocked |
| `RATE_LIMIT_USER_WRITES_PER_MINUTE` | `60` | Writes (anything but `GET`) per minute for one user |
| `RATE_LIMIT_USER_RUNS_PER_MINUTE` | `20` | Runs per minute for one user (runs also count as writes) |
| `RATE_LIMIT_NEW_WORKSPACES_PER_IP_PER_HOUR` | `5` | New accounts per hour from one visitor IP; each one gets its own workspace |
| `TRUSTED_PROXY` | `0` | Proxies in front of the API whose `X-Forwarded-For` entry is trusted. `0` ignores the header |
| `LIMIT_NOTICE` | empty | Text added to every limit error, for example how to get more capacity. Up to 300 characters |
| `LIMIT_NOTICE_URL` | empty | A link shown with the notice. Must start with `http://` or `https://` |

A public deployment should set the per-workspace cap and a shorter timeout, for example `MAX_CONCURRENT_RUNS_PER_WORKSPACE=2` and `RUN_TIMEOUT_SECONDS=30`.

## When a limit is reached

- **Too many runs at once:** `POST /flows/{id}/runs` answers `429` with code `run_limit` and a `Retry-After` header (seconds, never more than 5 and never more than the run timeout). `details.scope` is `app` or `workspace`. Nothing is queued: wait and send the request again. A refused request creates no run.
- **Run too long:** the run stops and is recorded as `failed` with the message `Run timed out after N seconds`. The response is `200`, like any other failure inside a flow.
- **Flow too big:** a draft over `MAX_NODES` or `MAX_EDGES` still saves, but validating or running it answers `422` with code `invalid_flow`. `details.errors` names `too_many_nodes` or `too_many_edges` and says how many there are. The editor shows the same error.
- **Too many flows:** `POST /flows` answers `409` with code `flow_limit_reached` and `details.limit` and `details.count`. Two requests sent at the same moment can both pass the check, so the count can go slightly over.
- **Too many requests:** any route can answer `429` with code `rate_limited`, a `Retry-After` header (seconds) and `details.scope`: `ip`, `ready`, `failed_auth`, `user`, `runs` or `new_workspaces`. Responses carry `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset` for the last limit that applied. Failed sign-ins count too: after `RATE_LIMIT_FAILED_AUTH_PER_MINUTE` of them, every request from that IP is refused until the minute passes.

When `LIMIT_NOTICE` is set, every limit error (`429`, `413` and `409`) also carries `details.notice`, plus `details.notice_url` if a link is set. The `message` stays the same, so clients keep matching on it. Show the notice as plain text, never as HTML. On a shared demo it can explain why the limit exists, for example: `This is a free demo on shared resources. To get more capacity, self-host it or sponsor the server.`

A request that is rejected for another reason (unknown flow, invalid input) never takes a slot.

## Client IP and proxies

Limits per IP need the real client address. Behind a platform proxy (Render, Fly, a load balancer) set `TRUSTED_PROXY` to the number of proxies in front of the API, for example `1` on Render. The API then reads the entry those proxies added to `X-Forwarded-For`, counting from the right, so a header the client made up is ignored. With `TRUSTED_PROXY=0` the header is ignored altogether and the connection address is used. IPv6 clients are grouped by their /64 network.

The web app calls the API from its own servers, so the API would only see those. The web app therefore sends the visitor's address in `X-Client-IP` (read from `AUTH_IP_HEADER`), and the API believes it only on requests signed with the web app's own token. The signed-in IP limit and the new-account limit use that address, so visitors do not share one limit just because they go through the same web server. `AUTH_IP_HEADER` must name a header your platform sets itself (the default `x-forwarded-for` is safe on Vercel, which overwrites it); a header the client can send lets anyone pick their own address.

The container starts uvicorn with `--no-proxy-headers`, so the connection address is always the real peer and `TRUSTED_PROXY` is the only thing that reads `X-Forwarded-For`.

## Notes

- Deleting a flow removes its runs. Their MLflow traces are not removed.
- Each limiter tracks at most 10,000 keys; a flood of distinct IPs can push out the oldest counters.
- Counts and rate limits are held in memory, so they are per server process and reset when it restarts. Run one instance, or accept that each instance counts on its own.
- The timeout is checked while a run waits, so it cannot interrupt a node that is busy computing.
- On shutdown the container waits up to 30 seconds for runs in progress. A run still going after that is cut off and leaves no record, because a run is saved when it ends. Keep `RUN_TIMEOUT_SECONDS` below that, and note that a platform may stop the container sooner.
