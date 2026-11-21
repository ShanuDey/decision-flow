Sends one prompt to a chat model on Groq and returns the reply in `body.choices.0.message.content`.

The model comes from the connection's default model. To use another one, change `model` in the body. Free-tier requests are rate limited per model, so an HTTP 429 means wait and retry.
