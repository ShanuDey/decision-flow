---
title: "HTTP Request"
---

Calls an HTTP API and makes the response available to the nodes after it.

| Setting | Meaning |
|---|---|
| `method` | `GET` (default), `POST`, `PUT`, `PATCH` or `DELETE` |
| `url` | A [template](../concepts/templates). Must start with `http://` or `https://`. [Secrets](../secrets) are not allowed here |
| `headers` | Header name to value. Values are templates and may use secrets. Headers that frame the message (`Host`, `Content-Length`, `Transfer-Encoding`, `Connection`, `Upgrade`, `TE`, `Trailer`, `Keep-Alive`, `Proxy-Connection`) are set by the server and are refused here |
| `query` | Query parameter name to value. Values are templates and may use secrets. They are encoded for you |
| `body_type` | `none` (default), `json`, `form` or `text` |
| `body` | The body, shaped by `body_type` (see below). Not allowed on `GET` |
| `timeout_seconds` | Optional. Never longer than the server's limit |
| `fail_on_error_status` | `false` (default) keeps a 4xx or 5xx answer as data. `true` fails the node |

## Body

| `body_type` | `body` is | Sent as |
|---|---|---|
| `json` | Any JSON. Every text value inside is a template | `application/json` |
| `form` | Names and text values | `application/x-www-form-urlencoded`, encoded field by field |
| `text` | One text template | `text/plain`, exactly as written |

In a JSON body each value is filled in separately, so an input cannot break out of the JSON. A value that is only one reference keeps its type: `"{{ input.amount }}"` sends a number. A `Content-Type` header you set yourself is used instead of the default.

```json
{
  "method": "POST",
  "url": "https://api.example.com/score",
  "headers": { "Authorization": "Bearer {{ secrets.SCORE_KEY }}" },
  "body_type": "json",
  "body": { "customer": "{{ input.customer_id }}", "amount": "{{ input.amount }}" }
}
```

## Output

The response is stored at `nodes.<id>.output`, where later nodes can read it:

| Key | Value |
|---|---|
| `status` | The HTTP status code |
| `ok` | `true` for a 2xx status |
| `headers` | Response headers, with lowercase names |
| `body` | The parsed JSON when the response is JSON, otherwise the text |
| `duration_ms` | How long the call took |
| `request` | The method and URL, and the names (not the values) of the headers and query parameters that were sent |

For example, `{{ nodes.call.output.body.score }}` in an [Assign](assign) or [End](end) value, or `nodes.call.output.status == 200` in a [Condition](condition). A node can read only nodes that run before it.

A redirect is not followed. The 3xx answer comes back as data, with its `location` header.

## When it fails

The node fails the run, naming itself, when the request cannot be made:

| Reason | Meaning |
|---|---|
| `blocked_destination` | The address is not allowed (see below) |
| `scheme_not_allowed`, `invalid_url`, `host_not_allowed` | The URL is not allowed here |
| `dns_failed`, `connect_failed`, `tls_failed` | The host could not be reached, or its certificate did not match its name |
| `timeout` | The call took longer than the timeout |
| `response_too_large` | The answer was bigger than the size limit |

A missing secret stops the run before any node starts.

## Which addresses can be called

All outgoing calls are checked before they are made. The name is looked up once, every address it gives is checked, and the connection goes to the address that was checked.

- The addresses used for cloud metadata (`169.254.x.x`), `0.0.0.0` and multicast are never allowed.
- With `ALLOW_PRIVATE_NETWORKS` on (the default), `localhost` and private ranges such as `10.x`, `172.16.x` and `192.168.x` work, over `http` or `https`. This suits a self-hosted install that calls its own services.
- With it off, only public addresses over `https` work. Turn it off on any shared deployment.
- `HTTP_ALLOWED_HOSTS` can limit calls to a list of hosts.

A flow cannot read the server's environment variables.

A header or URL that contains a line break is refused before anything is sent. The call identifies itself with a `User-Agent` of `decision-flow` unless you set your own, so a site that sees abuse can trace it to the server.

## Keep credentials safe

A secret goes wherever the flow sends it. Anyone who can edit a flow in a workspace can point a header at any address the server may call, so only give edit access to people you trust. On a shared server, set `HTTP_ALLOWED_HOSTS` so a flow can reach only hosts you have chosen.

The request is limited in size too: the URL, headers, query and body together cannot exceed `MAX_HTTP_RESPONSE_BYTES`, so a template cannot turn a large input into a huge request.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `ALLOW_PRIVATE_NETWORKS` | `true` | Allow `localhost` and private addresses, and `http`. Off on a shared deployment |
| `HTTP_ALLOWED_HOSTS` | empty (any host) | Comma-separated hosts the node may call. `*.example.com` matches subdomains. Write international names in their `xn--` form |
| `MAX_HTTP_RESPONSE_BYTES` | `5242880` | Largest response accepted, and the largest request the node will build |
| `HTTP_TIMEOUT_SECONDS` | `30` | Longest a call may take, including looking up the name and connecting |
| `DISABLED_NODE_TYPES` | empty | Comma-separated node types that flows may not use on this server, for example `http_request` |
