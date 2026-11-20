Fills an HTTP Request node that posts a message with `chat.postMessage`.

## Use

1. Install the template. It installs the Slack connection type with it.
2. Add the template to a flow and choose a Slack connection.
3. Pass `channel` (an id or name) and `text` as flow inputs.

Slack answers with HTTP 200 even on errors; check `ok` in the response body.
