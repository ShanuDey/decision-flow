Sends a question to a chat model and returns `answer`, using a Prompt node.

## Use

1. Create an OpenAI-compatible connection: set its base URL to your provider's (OpenAI, Groq, OpenRouter, Ollama and others), add the API key, and set a default model.
2. Start a new flow from this one and match the connection when asked. To switch provider later, change the connection, not the flow.
3. Run it with a `question`.

To change the answer style, edit the system instructions in the **Ask** node after you create your flow.
