"""A local OpenAI-style endpoint for tests: records each call and answers as told."""

import asyncio
import json
from collections import namedtuple
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

Seen = namedtuple("Seen", "target headers body")


@asynccontextmanager
async def chat_server(
    reply: str = "ok", status: int = 200, raw: bytes | None = None
) -> AsyncIterator[tuple[int, list[Seen]]]:
    """Answers every call with a chat completion holding `reply`, or with `raw` as the body."""
    seen: list[Seen] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode().split("\r\n")
        headers = {k.lower(): v for k, v in (h.split(": ", 1) for h in head[1:] if ": " in h)}
        body = await reader.readexactly(int(headers.get("content-length", "0")))
        seen.append(Seen(head[0].split()[1], headers, json.loads(body)))
        payload = raw
        if payload is None:
            completion = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "served-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
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
