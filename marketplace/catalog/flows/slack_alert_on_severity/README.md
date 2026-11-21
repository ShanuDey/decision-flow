Posts a message to a Slack channel when `severity` is `high`, and does nothing for any other value.

## Use

1. Install the flow. It installs the Slack connection type with it.
2. Create a Slack connection (see the Slack connection type for how to get a bot token), then start a new flow from this one and match the connection when asked.
3. Run it with `severity`, `channel` (an id or name) and `message`.

The flow returns `status`: `sent` or `skipped`. Slack answers with HTTP 200 even on errors; the request node checks the HTTP status only, so add a condition on the response body's `ok` if you need to catch those.
