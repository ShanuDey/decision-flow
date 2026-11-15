"""Turns recorded spans into the steps the trace view shows."""

from typing import Literal

from app.runs.schemas import RunStep
from app.tracing import TraceSpan

NS_PER_MS = 1_000_000
Kind = Literal["node", "llm", "tool", "parser", "other"]
KINDS: dict[str, Kind] = {"LLM": "llm", "CHAT_MODEL": "llm", "TOOL": "tool", "PARSER": "parser"}


def _kind(span: TraceSpan) -> Kind:
    if span.node_id is not None:
        return "node"
    return KINDS.get(span.span_type, "other")


def build_steps(spans: list[TraceSpan]) -> list[RunStep]:
    """Drops the run's root span (the earliest parentless one); its children become top level."""
    if not spans:
        return []
    root = min((s for s in spans if s.parent_id is None), key=lambda s: s.start_ns, default=None)
    origin = min(s.start_ns for s in spans)
    known = {s.id for s in spans if root is None or s.id != root.id}
    steps = [
        RunStep(
            id=s.id,
            parent_id=s.parent_id if s.parent_id in known else None,
            kind=_kind(s),
            node_id=s.node_id,
            node_type=s.node_type,
            name=s.name,
            status="ok" if s.ok else "failed",
            error=s.error,
            start_offset_ms=round((s.start_ns - origin) / NS_PER_MS, 3),
            duration_ms=round((s.end_ns - s.start_ns) / NS_PER_MS, 3),
            input=s.input,
            output=s.output,
        )
        for s in sorted(spans, key=lambda s: s.start_ns)
        if root is None or s.id != root.id
    ]
    return steps
