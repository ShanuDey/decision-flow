"""A local OpenAI-style endpoint for tests: records each call and answers as told."""

import asyncio
import json
import re
from collections import namedtuple
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

Seen = namedtuple("Seen", "target headers body")


def chunks(completion: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    choice = completion["choices"][0]
    message = choice["message"]
    base = {"id": completion["id"], "object": "chat.completion.chunk", "model": completion["model"]}

    def delta(body: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return base | {"choices": [{"index": 0, "delta": body, "finish_reason": finish}]}

    out = [delta({"role": "assistant", "content": ""})]
    out += [
        delta({"content": word}) for word in re.findall(r"\S+\s*", message.get("content") or "")
    ]
    for i, call in enumerate(message.get("tool_calls") or []):
        out.append(delta({"tool_calls": [{"index": i, **call}]}))
    out.append(delta({}, choice["finish_reason"]))
    if (request.get("stream_options") or {}).get("include_usage"):
        out.append(base | {"choices": [], "usage": completion["usage"]})
    return out


async def stream(
    writer: asyncio.StreamWriter, completion: dict[str, Any], request: dict[str, Any], pace: float
) -> None:
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n")
    for item in [*chunks(completion, request), "[DONE]"]:
        data = item if isinstance(item, str) else json.dumps(item)
        writer.write(f"data: {data}\n\n".encode())
        await writer.drain()
        await asyncio.sleep(pace)
    writer.close()


@asynccontextmanager
async def chat_server(
    reply: str = "ok",
    status: int = 200,
    raw: bytes | None = None,
    script: list[dict[str, Any]] | None = None,
    pace: float = 0,
) -> AsyncIterator[tuple[int, list[Seen]]]:
    """Answers every call with a chat completion holding `reply`, or with `raw` as the body.

    With `script`, call N is answered with message N (the last repeats). A message may carry
    `finish_reason` and `usage` keys, which are lifted out of it.

    A request with `stream: true` is answered as server-sent chunks, a word at a time, `pace`
    seconds apart; usage comes last when `stream_options.include_usage` is set.
    """
    seen: list[Seen] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode().split("\r\n")
        headers = {k.lower(): v for k, v in (h.split(": ", 1) for h in head[1:] if ": " in h)}
        body = await reader.readexactly(int(headers.get("content-length", "0")))
        seen.append(Seen(head[0].split()[1], headers, json.loads(body)))
        payload = raw
        if payload is None:
            message = {"role": "assistant", "content": reply}
            finish = "stop"
            usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
            if script:
                message = dict(script[min(len(seen), len(script)) - 1])
                finish = message.pop("finish_reason", "stop")
                usage = message.pop("usage", usage)
            completion = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "served-model",
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": usage,
            }
            if status == 200 and seen[-1].body.get("stream"):
                await stream(writer, completion, seen[-1].body, pace)
                return
            payload = json.dumps(completion).encode()
        start = f"HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nConnection: close\r\n"
        writer.write(f"{start}Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1], seen
    finally:
        server.close()
        await server.wait_closed()
