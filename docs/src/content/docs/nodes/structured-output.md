---
title: "Structured output"
---

Asks a chat model a question and returns its answer as typed fields, such as a name, a score or a yes or no, that later nodes can read directly. Use it when you need values, not prose. For a free-text reply, use [Prompt](prompt).

It works with any provider that has an OpenAI-style API, through an OpenAI-compatible [connection](../connections), like the Prompt node.

| Setting | Meaning |
|---|---|
| `connection_id` | The connection to use. It must be an OpenAI-compatible connection |
| `prompt` | The message to send, as a [template](../concepts/templates) |
| `system` | Optional instructions sent before the prompt, also a template |
| `fields` | The values to return. Each has a `name`, a `type` and an optional `description` that helps the model |
| `mode` | `schema` (default) asks the provider to enforce the structure. `json` only asks for a JSON object and puts the structure in the instructions |
| `model` | Optional template for the model name. Empty uses the connection's default model |
| `temperature`, `max_tokens`, `timeout_seconds` | Optional. Options you leave empty are not sent |

## Field types

| Type | The model returns |
|---|---|
| `string` | Text |
| `number` | A number |
| `boolean` | `true` or `false` |
| `enum` | One of the `values` you list |
| `array` | A list of text values |

A field name uses letters, digits and underscores and cannot start with a digit, because later nodes read it by name.

```json
{
  "connection_id": "5f0c1a3e-8d2b-4c7e-9a41-2b6f7d8e9c10",
  "prompt": "Extract the contact details from: {{ input.text }}",
  "fields": [
    { "name": "name", "type": "string", "description": "The person's full name" },
    { "name": "urgent", "type": "boolean" },
    { "name": "topic", "type": "enum", "values": ["billing", "support", "sales"] }
  ]
}
```

## Output

Each field is stored at `nodes.<id>.output.<name>`, for example `{{ nodes.extract.output.name }}` in an [End](end) or [Assign](assign) value, or `nodes.extract.output.urgent` in a [Condition](condition). The names are known up front, so Validate flags a reference to a field that does not exist.

## When the answer does not fit

The answer is checked in both modes. The run fails at this node when the model does not answer with JSON, when a field is missing, or when a value has the wrong type or is not in the list of allowed values. The message names every field that is wrong. Extra fields the model adds are ignored.

If a provider or model rejects the structure, switch `mode` to `json`. Smaller models may need a clearer prompt or a `description` on each field.

Errors from the provider, such as a rejected key or a rate limit, are the same as for the [Prompt](prompt) node.
