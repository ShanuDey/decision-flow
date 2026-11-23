Sends a text to a chat model and returns `summary`, at most three sentences. It works with any provider that has an OpenAI-style API, such as OpenAI, Groq, OpenRouter or Ollama.

## Use

1. Create an OpenAI-compatible connection. Set its base URL to your provider's, add the API key, and set a default model.
2. Start a new flow from this one and match the connection when asked. The flow calls `{{ connection.base_url }}/chat/completions` and uses the connection's default model, so to switch provider you change the connection, not the flow.
3. Run it with `text`.

To change the instructions, edit the system message in the **Summarize** node after you create your flow.
