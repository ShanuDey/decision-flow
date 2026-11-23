---
title: "Talk to an agent from your app"
---

Your own app can chat with an agent over HTTP. You start a conversation, send messages, and read the answers. The server keeps the history, so each message only needs its text. Every conversation belongs to one person of yours, so your customers never see each other's chats.

This page covers the basics. Every route, field and error is in the [API reference](/docs/api).

## Before you start

1. Create the agent in the web app, give it a connection, instructions and any flows it may run as tools, and try it in the **Chats** tab.
2. Open **Settings → API keys** and create a key with the agent scopes your app needs:

| Scope | Lets the key |
|---|---|
| `agents:chat` | Start conversations, send messages, delete a conversation |
| `agents:read` | List agents, list and read conversations, read the steps of an answer |
| `agents:manage` | Create, change and delete agents |

A key that only chats needs `agents:chat`. Add `agents:read` if your app shows history. Scopes are independent, and a key without a scope gets `403`.

3. Keep the key on your server. Your browser or mobile code should call your own backend, and your backend calls Decision Flow. Anyone holding the key can act within its scopes.

All calls go to `https://<web-url>/api/v1` with the key as a bearer token:

```
Authorization: Bearer df_live_...
```

## Who is the person

Send your own id for the person in the `X-External-User-Id` header: a customer id, an email, anything up to 256 characters without control characters.

```
X-External-User-Id: customer-4821
```

- A conversation started with an id belongs to that person. A request that names a person can only reach that person's conversations, and gets `404` for anyone else's.
- The id is yours. Decision Flow does not check it, so your backend must send the right one for the signed-in user.
- The same id in two workspaces is two different people. If several of your apps share one workspace, prefix the ids, for example `web:4821` and `mobile:4821`, so they cannot collide.
- To list conversations, the header is required. You get that person's conversations only.

### Visitors you cannot name

If you send no id when you start a conversation, the server makes one up (it starts with `anon-`) and returns it as `external_user_id`, with `"anonymous": true`. Keep it with the visitor, for example in a cookie your backend sets, and send it back on later calls so the same visitor stays together. A conversation without that id can only be reached by its own conversation id, which is a long random value.

## Start a conversation

```bash
curl -X POST https://<web-url>/api/v1/agents/$AGENT_ID/threads \
  -H "Authorization: Bearer $KEY" \
  -H "X-External-User-Id: customer-4821"
```

```json
{
  "id": "5d1e8c1a-3f0b-4d6e-9a0e-7a1c2b9f4e10",
  "agent_id": "63fac388-fa87-46a2-b523-e3161a9d6bcd",
  "title": "",
  "external_user_id": "customer-4821",
  "source": "api",
  "anonymous": false,
  "created_at": "2026-11-23T10:15:00Z",
  "updated_at": "2026-11-23T10:15:00Z"
}
```

The `id` is the conversation id. Store it next to your user. The `title` fills in from the first message.

## Send a message and wait for the answer

```bash
curl -X POST https://<web-url>/api/v1/agents/$AGENT_ID/threads/$THREAD_ID/messages \
  -H "Authorization: Bearer $KEY" \
  -H "X-External-User-Id: customer-4821" \
  -H "Content-Type: application/json" \
  -d '{"content": "Check income 45000 and credit score 720"}'
```

```json
{
  "user_message": { "id": "...", "seq": 1, "role": "user", "content": "Check income 45000 and credit score 720" },
  "reply": {
    "id": "...",
    "seq": 2,
    "role": "assistant",
    "content": "The applicant is approved.",
    "steps": [
      { "name": "check_loan_eligibility", "arguments": { "income": 45000, "credit_score": 720 }, "result": "...", "is_error": false }
    ],
    "usage": { "prompt_tokens": 322, "completion_tokens": 124, "total_tokens": 446 },
    "model": "openai/gpt-oss-20b",
    "traced": true
  }
}
```

`steps` lists the flows the agent ran as tools. The call returns when the agent has answered, which can take a while if it runs several flows. Nothing is stored when a turn fails.

A message is 1 to 20,000 characters. Send one message at a time to a conversation: a second one that is answered at the same time gets `409 thread_busy`.

## Stream the answer

`POST /agents/{agent_id}/invoke` sends the message and streams the answer as server-sent events in the open [AG-UI](https://docs.ag-ui.com) format, so you can show text as it is written and show tool calls as they finish.

```bash
curl -N -X POST https://<web-url>/api/v1/agents/$AGENT_ID/invoke \
  -H "Authorization: Bearer $KEY" \
  -H "X-External-User-Id: customer-4821" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "threadId": "'$THREAD_ID'",
    "runId": "1",
    "state": {},
    "messages": [{"id": "1", "role": "user", "content": "Check income 45000 and credit score 720"}],
    "tools": [],
    "context": [],
    "forwardedProps": {}
  }'
```

Only `threadId` and the last user message in `messages` are used, because the server keeps the history. The other fields are accepted and ignored.

Each event is one `data: {json}` line followed by a blank line, in this order:

| Event | Meaning |
|---|---|
| `RUN_STARTED` | The answer began |
| `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` | A piece of the model's text. Show the text of the latest message only, because a model call that asks for a flow may write a few words first |
| `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `TOOL_CALL_RESULT` | The agent ran a flow. They arrive together once it finishes |
| `CUSTOM` named `message.stored` | The stored `user_message` and `reply`, as in the plain response |
| `RUN_FINISHED` | Done |
| `RUN_ERROR` | The answer failed. The `code` is one of the errors below, and nothing is stored |

Lines that start with `:` are keep-alive comments sent while the agent is quiet. Your parser should ignore them.

Send `Accept: application/json` instead and the same route waits and returns the plain response shown above.

## Read history

```bash
# One person's conversations, newest first
curl https://<web-url>/api/v1/agents/$AGENT_ID/threads \
  -H "Authorization: Bearer $KEY" -H "X-External-User-Id: customer-4821"

# One conversation with all its messages, oldest first
curl https://<web-url>/api/v1/agents/$AGENT_ID/threads/$THREAD_ID \
  -H "Authorization: Bearer $KEY" -H "X-External-User-Id: customer-4821"
```

The steps of an answer (each model call and each flow it ran, with timings) are at `GET /agents/{agent_id}/threads/{thread_id}/messages/{message_id}/steps`. They need `agents:read`, and are the same steps you see in the [trace](traces).

To delete a conversation and all its messages, call `DELETE /agents/{agent_id}/threads/{thread_id}`. This cannot be undone.

## Errors

| Status | Code | Meaning |
|---|---|---|
| `401` | `missing_key`, `invalid_key`, `key_expired`, `key_revoked` | The key is missing, wrong, expired or revoked |
| `403` | `insufficient_scope` | The key lacks the scope this call needs |
| `404` | `not_found` | No such agent, conversation or message, or the conversation belongs to someone else |
| `409` | `thread_busy` | Another message in this conversation was answered at the same time |
| `422` | `agent_not_ready` | The agent has no working connection or model yet |
| `422` | `agent_stopped` | The agent hit one of its limits (iterations, tokens or time) before answering |
| `422` | `external_user_id_required` | A list needs `X-External-User-Id` |
| `422` | `invalid_external_user_id` | The id is empty, too long or has control characters |
| `502` | `model_failed` | The model provider refused or could not be reached |
| `429` | `run_limit`, `rate_limited` | Too many answers at once, or too many requests. Wait for `Retry-After` |

For a streamed answer, a failure after the stream starts arrives as a `RUN_ERROR` event with the same `code`. A problem found before the stream starts, such as an unknown conversation, is a normal error response.

## Limits

- **History.** The model sees the latest 40 messages of a conversation, up to 60,000 characters. Older messages stay stored and visible to you but are not sent.
- **Time.** One answer may take up to `RUN_TIMEOUT_SECONDS` (300 by default), and an agent's own `max_seconds`, iteration and token limits apply inside that. See [limits](limits).
- **Hosting.** A platform that cuts requests after a minute or so will cut a long answer too. Self-hosted servers have no such cap.
- **Concurrency.** Answers count toward the same run limits as flow runs.
