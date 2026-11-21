"""One chat call to an OpenAI-compatible endpoint, through a connection and the outbound policy."""

import asyncio
import json
from typing import Any

import httpx
import openai
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import Field

from app.engine.base import FrozenBaseModel
from app.engine.connections import ResolvedConnection, host_allowed
from app.engine.llm.urls import split_base_url
from app.engine.redact import Redactor
from app.engine.run_secrets import RunSecrets
from app.security.ssrf import FRAMING_HEADERS, OutboundPolicy
from app.security.transport import BlockedRequest, guarded_client

MAX_PROVIDER_MESSAGE = 300
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")
# The SDK adds these from the server's environment; they belong to the operator, not the provider.
ENVIRONMENT_HEADERS = ("openai-organization", "openai-project")
STATUS_HINTS = {
    401: "the provider rejected the key",
    402: "the provider needs payment or credit",
    403: "the provider refused the request",
    404: "the provider does not know that model or endpoint",
    429: "the provider's rate limit was hit; wait and retry",
}


class ChatReply(FrozenBaseModel):
    text: str
    model: str
    finish_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


def require_base_url(connection: ResolvedConnection) -> str:
    base = connection.values.get("base_url", "")
    if not base:
        raise ValueError(
            f"connection '{connection.name}' has no base URL; use an OpenAI-compatible connection"
        )
    return base


def _provider_message(body: bytes, redactor: Redactor) -> str:
    # Masked before it is cut, so a secret split by the cut cannot slip through.
    text = " ".join(redactor.text(body.decode("utf-8", "replace")).split())
    try:
        data = json.loads(text)
    except ValueError:
        return text[:MAX_PROVIDER_MESSAGE]
    error = data.get("error") if isinstance(data, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    if not isinstance(message, str) and isinstance(data, dict):
        message = data.get("message")
    return " ".join((message if isinstance(message, str) else text).split())[:MAX_PROVIDER_MESSAGE]


def _blocked(exc: BaseException | None) -> BlockedRequest | None:
    while exc is not None:
        if isinstance(exc, BlockedRequest):
            return exc
        exc = exc.__cause__
    return None


def _failure(exc: Exception, connection: ResolvedConnection) -> ValueError:
    if (blocked := _blocked(exc)) is not None:
        return ValueError(f"request failed ({blocked.error.code}): {blocked.error.message}")
    if isinstance(exc, openai.APITimeoutError | TimeoutError):
        return ValueError("request failed (timeout): The request timed out")
    if isinstance(exc, openai.APIStatusError):
        hint = STATUS_HINTS.get(exc.status_code, "the provider answered with an error")
        redactor = Redactor(RunSecrets(connections={connection.id: connection}))
        detail = _provider_message(exc.response.content, redactor)
        return ValueError(f"{hint} (HTTP {exc.status_code}){': ' + detail if detail else ''}")
    if isinstance(exc, openai.APIConnectionError):
        return ValueError("request failed (connect_failed): Could not connect to the host")
    return ValueError("the provider's reply is not a chat completion")


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    blocks = [b if isinstance(b, str) else b.get("text", "") for b in content]
    return "".join(b for b in blocks if isinstance(b, str))


def _reply(message: BaseMessage, requested: str) -> ChatReply:
    meta = getattr(message, "response_metadata", None) or {}
    given = meta.get("token_usage") or {}
    usage = {k: given[k] for k in USAGE_KEYS if isinstance(given.get(k), int)}
    finish = meta.get("finish_reason")
    return ChatReply(
        text=_text(message),
        model=str(meta.get("model_name") or meta.get("model") or requested),
        finish_reason=finish if isinstance(finish, str) else None,
        usage=usage,
    )


async def chat_completion(
    policy: OutboundPolicy,
    connection: ResolvedConnection,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatReply:
    """Raises ValueError with a message a flow author can act on. Unset options are not sent."""
    base, query = split_base_url(require_base_url(connection))
    host = httpx.URL(base).host
    if not host_allowed(host, connection.hosts):
        allowed = ", ".join(connection.hosts)
        raise ValueError(f"connection '{connection.name}' may only call {allowed}, not {host}")
    headers = {
        name: value.get_secret_value()
        for name, value in connection.headers.items()
        if name.lower() not in FRAMING_HEADERS
    }
    bearer = headers.pop("Authorization", "")
    api_key = bearer.removeprefix("Bearer ") if bearer.startswith("Bearer ") else ""
    if bearer and not api_key:
        headers["Authorization"] = bearer
    client = guarded_client(policy, drop_headers=ENVIRONMENT_HEADERS)
    options: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens}
    try:
        async with asyncio.timeout(policy.timeout_seconds):
            chat = ChatOpenAI(
                model=model,
                api_key=api_key or "unused",
                base_url=base,
                default_query=query or None,
                default_headers=headers or None,
                http_async_client=client,
                max_retries=0,
                openai_proxy=None,
                timeout=policy.timeout_seconds,
                **{k: v for k, v in options.items() if v is not None},
            )
            message = await chat.ainvoke(messages)
    except Exception as exc:
        raise _failure(exc, connection) from None
    finally:
        await client.aclose()
    return _reply(message, model)
