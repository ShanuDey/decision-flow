import asyncio
import time
from typing import Any, Literal

from app.engine.base import FrozenBaseModel
from app.engine.compiler import CompiledFlow
from app.engine.inputs import validate_input
from app.engine.observer import NodeError, NullObserver, Observer
from app.engine.redact import RedactingObserver, Redactor
from app.engine.run_secrets import RunSecrets
from app.security.ssrf import OutboundPolicy


class RunError(FrozenBaseModel):
    node_id: str
    message: str


class RunResult(FrozenBaseModel):
    status: Literal["succeeded", "failed"]
    output: dict[str, Any] | None
    error: RunError | None
    duration_ms: int


async def _failed(
    observer: Observer, redactor: Redactor, started: float, node_id: str, message: str
) -> RunResult:
    ms = int((time.perf_counter() - started) * 1000)
    message = redactor.text(message)
    await observer.run_finished("failed", message)
    return RunResult(
        status="failed",
        output=None,
        error=RunError(node_id=node_id, message=message),
        duration_ms=ms,
    )


async def run_flow(
    flow: CompiledFlow,
    payload: dict[str, Any],
    observer: Observer | None = None,
    timeout_seconds: float = 0,
    secrets: RunSecrets | None = None,
    outbound: OutboundPolicy | None = None,
) -> RunResult:
    """Raises InputValidationError before anything runs; a failure inside the flow is a result."""
    inputs = validate_input(flow.start.data.inputs, payload)
    state = {"input": inputs}
    redactor = Redactor(secrets)
    observer = RedactingObserver(observer or NullObserver(), redactor)
    config = {
        "configurable": {
            "observer": observer,
            "secrets": secrets or RunSecrets(),
            "outbound": outbound,
        }
    }
    await observer.run_started(inputs)
    started = time.perf_counter()
    try:
        # Fires at an await: synchronous node code is not interrupted.
        async with asyncio.timeout(timeout_seconds or None):
            final = await flow.graph.ainvoke(state, config=config)
    except NodeError as exc:
        return await _failed(observer, redactor, started, exc.node_id, exc.message)
    except TimeoutError:
        return await _failed(
            observer, redactor, started, "", f"Run timed out after {timeout_seconds:g} seconds"
        )
    ms = int((time.perf_counter() - started) * 1000)
    output = redactor.apply(final["_output"])
    await observer.run_finished("succeeded", None, output)
    return RunResult(status="succeeded", output=output, error=None, duration_ms=ms)
