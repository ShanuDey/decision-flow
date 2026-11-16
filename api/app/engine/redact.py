"""Masks secret values and credential headers before anything is recorded or returned."""

import json
from typing import Any
from urllib.parse import quote, quote_plus

from app.engine.observer import NodeInfo, NodeStatus, Observer, RunStatus
from app.engine.run_secrets import RunSecrets

MASK = "[REDACTED]"
SENSITIVE_KEYS = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "api-key"}
)


def _sensitive(key: Any) -> bool:
    return isinstance(key, str) and key.lower() in SENSITIVE_KEYS


class Redactor:
    def __init__(self, secrets: RunSecrets | None = None) -> None:
        forms: set[tuple[str, str]] = set()
        for name, value in (secrets.as_scope() if secrets else {}).items():
            if not value:
                continue
            # The same value also shows up JSON-escaped in error text and URL-encoded in URLs.
            for text in {value, json.dumps(value)[1:-1], quote(value, safe=""), quote_plus(value)}:
                forms.add((text, f"[REDACTED:{name}]"))
        self._forms = sorted(forms, key=lambda form: len(form[0]), reverse=True)

    def text(self, value: str) -> str:
        for secret, mask in self._forms:
            value = value.replace(secret, mask)
        return value

    def apply(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return self._dict(value)
        if isinstance(value, list | tuple):
            return [self.apply(item) for item in value]
        return value

    def _dict(self, value: dict[Any, Any]) -> dict[Any, Any]:
        # A header given as {"name": "Authorization", "value": ...} is masked like a keyed one.
        pair = _sensitive(value.get("name")) and "value" in value
        out: dict[Any, Any] = {}
        for key, item in value.items():
            out[key] = (
                self._credential(item)
                if _sensitive(key) or (pair and key == "value")
                else self.apply(item)
            )
        return out

    def _credential(self, value: Any) -> Any:
        if value is None:
            return None
        masked = self.apply(value)
        # A known secret is named in the mask; anything else in a credential header is hidden.
        return masked if isinstance(value, str) and masked != value else MASK


class RedactingObserver:
    """Wraps the run's observer so no payload reaches it unmasked."""

    def __init__(self, inner: Observer, redactor: Redactor) -> None:
        self._inner = inner
        self._redactor = redactor

    async def run_started(self, inputs: dict[str, Any]) -> None:
        await self._inner.run_started(self._redactor.apply(inputs))

    async def node_started(self, node: NodeInfo, inputs: dict[str, Any]) -> None:
        await self._inner.node_started(node, self._redactor.apply(inputs))

    async def node_finished(
        self,
        node: NodeInfo,
        status: NodeStatus,
        duration_ms: int,
        error: str | None,
        outputs: Any = None,
    ) -> None:
        await self._inner.node_finished(
            node, status, duration_ms, self._redactor.apply(error), self._redactor.apply(outputs)
        )

    async def run_finished(
        self, status: RunStatus, error: str | None, outputs: dict[str, Any] | None = None
    ) -> None:
        await self._inner.run_finished(
            status, self._redactor.apply(error), self._redactor.apply(outputs)
        )
