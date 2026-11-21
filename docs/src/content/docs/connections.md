---
title: "Connections"
---

A connection holds the credentials for a service, such as an API key. Pick it in an [HTTP Request](nodes/http-request) node and the credentials are added to the request for you, so you do not write them into the flow. Connections belong to a workspace. Their credentials are stored encrypted, and once saved they cannot be read back: you can replace them or delete the connection.

## Add a connection

1. Open **Connections** in the sidebar and choose **Add connection**.
2. Pick a service from the list. **Built-in** services come with the app, **Installed** ones came from the [Marketplace](marketplace), and **Custom** covers a service that is not listed.
3. Fill in the form. The name is filled in for you and you can change it.
4. Choose **Add**.

| Type | What it sends |
|---|---|
| OpenAI-compatible | `Authorization: Bearer <key>` to the base URL you set, plus an optional default model. The default URL is OpenAI; set another for OpenRouter, Ollama or any provider with an OpenAI-style API |
| Bearer token | `Authorization: Bearer <token>` to the hosts you list |
| Basic auth | A username and password as HTTP Basic auth, to the hosts you list |
| API key in a header | Your key in a header you name, to the hosts you list |

## Where a credential can go

A connection only sends its credentials to hosts it allows. OpenAI-compatible allows the host of its base URL. A service from the Marketplace allows its own host. Custom types allow the hosts you list, such as `api.example.com` or `*.example.com`. If a node's URL points anywhere else, the run stops before anything is sent and the error names the host.

## Use one in a flow

In an HTTP Request node, choose it under **Connection**. A header you set in the node itself wins over the connection's. The credentials are masked in traces and errors, including the encoded form Basic auth sends.

A field in the node can read the connection's plain settings, such as `{{ connection.base_url }}` or `{{ connection.default_model }}`. The API key and other secret fields are never available this way. The node must have a connection picked, and the run stops with an error naming the value when the connection does not have it. A trailing `/` on a URL setting is removed, so `{{ connection.base_url }}/chat/completions` is always well formed.

Some types have a **Test** button on the Connections page that calls the service's check endpoint with the saved credentials.

## Delete a connection

A connection that a flow uses cannot be deleted until you pick another one in that flow. The error lists the flows. You can delete it anyway, and those flows then fail until you update them.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `ENCRYPTION_KEY` | none | Required to save a connection or a [secret](secrets) |
| `MAX_CONNECTIONS_PER_WORKSPACE` | `0` (off) | Most connections one workspace can hold. Editing one does not count |
