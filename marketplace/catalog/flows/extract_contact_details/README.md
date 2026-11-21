Reads a message and returns `name`, `company`, `topic` (billing, support, sales or other) and `urgent`, using a Structured output node.

## Use

1. Create an OpenAI-compatible connection with your provider's base URL, an API key and a default model. The model must be able to follow a JSON schema; if a provider rejects it, set the node's mode to "Ask for a JSON object".
2. Start a new flow from this one and match the connection when asked.
3. Run it with a `message`.

Add or change the fields in the **Extract** node after you create your flow. Each field you add can be read by later nodes as `nodes.extract.output.<name>`.
