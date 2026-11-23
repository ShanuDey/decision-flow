---
title: "Prompt"
---

Asks a chat model one question and makes its text available to the nodes after it. It talks to any provider with an OpenAI-style API, such as OpenAI, Groq, OpenRouter or a local Ollama, through a [connection](../connections).

| Setting | Meaning |
|---|---|
| `connection_id` | The connection to use. It must be an OpenAI-compatible connection, because the node calls the connection's base URL followed by `/chat/completions` |
| `prompt` | The message to send, as a [template](../concepts/templates) |
| `system` | Optional instructions sent before the prompt, also a template |
| `model` | Optional template for the model name. Empty uses the connection's default model |
| `temperature` | Optional, from 0 to 2. Empty uses the provider's default |
| `max_tokens` | Optional limit on the length of the reply. Empty uses the provider's default |
| `timeout_seconds` | Optional. Never longer than the server's limit |

Options you leave empty are not sent, so the provider's own defaults apply. Leave `temperature` and `max_tokens` empty unless you need them: some newer models reject a custom temperature, and `max_tokens` is sent as `max_completion_tokens`.

In the editor, pick the connection, write the prompt, and leave the model empty to use the connection's default. Templates can read flow inputs and earlier node outputs, such as `{{ input.text }}`. They cannot use secrets, because a prompt is sent to the model and recorded in traces. The key stays in the connection.

```json
{
  "connection_id": "5f0c1a3e-8d2b-4c7e-9a41-2b6f7d8e9c10",
  "system": "Summarize the text in at most three sentences.",
  "prompt": "{{ input.text }}",
  "max_tokens": 200
}
```

## Output

Later nodes read the reply as `nodes.<id>.output`:

| Field | Meaning |
|---|---|
| `text` | The model's reply. Empty when the model returned no text |
| `model` | The model that answered, as the provider reports it |
| `finish_reason` | Why the reply ended, such as `stop` or `length` |
| `usage` | Token counts the provider reports: `prompt_tokens`, `completion_tokens` and `total_tokens` |

For example, `{{ nodes.ask.output.text }}` in an [End](end) or [Assign](assign) value. A node can read only nodes that run before it.

## Errors

The run fails at this node, and the message says what to do:

| Provider answer | Meaning |
|---|---|
| 401 | The key was rejected. Replace it on the connection |
| 402 | The provider needs payment or credit |
| 403 | The provider refused the request, for example a model your plan does not include |
| 404 | The provider does not know that model or endpoint |
| 429 | A rate limit was hit. Wait and retry |

A base URL may carry a query such as `?api-version=1`: the endpoint is added to the path and the query is kept. Requests go through the server's outbound rules like the HTTP Request node does, and are never redirected, so a blocked address is refused with an error that does not say what is behind it. The provider's own message is quoted after the status. A connection can only send its key to the hosts it allows, so a connection to one provider cannot be pointed at another.
