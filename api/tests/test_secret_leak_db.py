import asyncio
import json
import time
from urllib.parse import parse_qs, quote, quote_plus, urlsplit

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import tracing
from app.engine.run_secrets import RunSecrets
from app.flows.store import FlowStore
from app.limits import Limits
from app.runs.service import run_draft
from app.runs.store import RunStore
from app.secrets.crypto import SecretBox
from app.secrets.service import load_run_secrets, put_secret
from app.secrets.store import SecretStore
from app.security.ssrf import OutboundPolicy
from app.settings import Settings
from tests.db_fixtures import SessionFactory, anyio_backend, make_member  # noqa: F401
from tests.test_node_http_request import flow as http_flow
from tests.test_node_http_request import serve

pytestmark = [pytest.mark.db, pytest.mark.anyio]

# Characters that show up escaped in JSON and encoded in URLs.
SECRET = 'pa"ss/w&rd-1234 xyz'
MASKED = "[REDACTED:API_KEY]"


def forms(value: str) -> set[str]:
    return {value, json.dumps(value)[1:-1], quote(value, safe=""), quote_plus(value)}


def tables_containing(url: str, needle: str) -> set[tuple[str, str]]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = connection.execute(
                text(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE table_schema IN ('public', 'mlflow') AND table_type = 'BASE TABLE'"
                )
            ).all()
            return {
                (schema, table)
                for schema, table in tables
                if connection.execute(
                    text(
                        f'SELECT count(*) FROM "{schema}"."{table}" t '
                        "WHERE position(:n IN t::text) > 0"
                    ),
                    {"n": needle},
                ).scalar()
            }
    finally:
        engine.dispose()


async def test_a_secret_leaves_no_trace_in_any_table_after_a_real_run(
    sessions: SessionFactory, postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = await make_member(sessions)
    box = SecretBox([Fernet.generate_key().decode()])
    async with sessions() as session:
        await put_secret(
            SecretStore(session), box, member, "API_KEY", SECRET, Limits(_env_file=None)
        )

    uri = (
        make_url(postgres_url)
        .update_query_dict({"options": "-csearch_path=mlflow"})
        .render_as_string(hide_password=False)
    )
    settings = Settings(_env_file=None, database_url=postgres_url, mlflow_tracking_uri=uri)
    monkeypatch.setattr(tracing, "_configured", False)
    monkeypatch.setattr(tracing, "_warmup", None)
    tracing.warm_up(settings)
    assert await tracing.ready() is True

    async def load(names: set[str]) -> RunSecrets:
        async with sessions() as session:
            return await load_run_secrets(SecretStore(session), lambda: box, member, names)

    async with serve() as (port, received):
        draft = http_flow(
            {
                "method": "POST",
                "url": f"http://127.0.0.1:{port}/echo",
                "headers": {"Authorization": "Bearer {{ secrets.API_KEY }}"},
                "query": {"key": "{{ secrets.API_KEY }}"},
                "body_type": "json",
                "body": {"token": "{{ secrets.API_KEY }}"},
            },
            [
                {"name": "seen", "type": "string", "value": "{{ nodes.call.output.body.body }}"},
                {
                    "name": "target",
                    "type": "string",
                    "value": "{{ nodes.call.output.body.target }}",
                },
            ],
        )
        async with sessions() as session:
            stored_flow = await FlowStore(session).create_flow(member, "Leak check", draft)
        async with sessions() as session:
            run = await run_draft(
                RunStore(session),
                member,
                stored_flow,
                {},
                lambda name: tracing.MlflowObserver(settings, name),
                load,
                outbound=OutboundPolicy(allow_private=True, max_bytes=100_000, timeout_seconds=5),
            )

    (request,) = received
    assert request["headers"]["authorization"] == f"Bearer {SECRET}"
    assert parse_qs(urlsplit(request["target"]).query)["key"] == [SECRET]
    assert json.loads(request["body"]) == {"token": SECRET}
    assert run.status == "succeeded", run.error
    assert MASKED in run.output["seen"] and MASKED in run.output["target"]

    await asyncio.to_thread(tracing.flush)
    assert run.mlflow_trace_id is not None
    deadline = time.monotonic() + 15
    spans: list = []
    while not spans and time.monotonic() < deadline:
        trace = await asyncio.to_thread(tracing.mlflow.get_trace, run.mlflow_trace_id)
        spans = list(trace.data.spans) if trace else []
        if not spans:
            await asyncio.sleep(0.2)
    assert spans

    leaked = {form: tables_containing(postgres_url, form) for form in forms(SECRET)}
    assert leaked == {form: set() for form in forms(SECRET)}

    seen_masked = tables_containing(postgres_url, MASKED)
    assert ("public", "runs") in seen_masked
    assert any(schema == "mlflow" for schema, _ in seen_masked)
