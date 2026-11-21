import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.catalog.flow_file import CatalogFlow
from app.catalog.index import build_index
from app.catalog.source import load_files
from app.engine.compiler import compile_graph
from app.engine.runtime import run_flow
from app.engine.templates import render
from app.engine.validate import parse_graph
from scripts.build_catalog_index import MARKETPLACE
from tests.test_catalog_index import put, template_file, type_file
from tests.test_catalog_router import OTHER, install

pytestmark = pytest.mark.anyio

SHIPPED = [f for f in load_files(MARKETPLACE / "catalog") if f.kind == "flow"]
CONNECTION = str(uuid.uuid4())
OTHER_SLOT = {"type": "acme", "name": "Other"}


def flow_file() -> dict[str, Any]:
    draft = {
        "schema_version": 1,
        "variables": [],
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "name": "Start",
                "position": {"x": 0, "y": 0},
                "data": {"inputs": [{"name": "who", "type": "string", "required": True}]},
            },
            {
                "id": "ping",
                "type": "http_request",
                "name": "Ping",
                "position": {"x": 200, "y": 0},
                "data": {"url": "https://api.acme.test/ping", "connection_id": CONNECTION},
            },
            {
                "id": "end",
                "type": "end",
                "name": "End",
                "position": {"x": 400, "y": 0},
                "data": {"outputs": [{"name": "ok", "type": "string", "value": "yes"}]},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "ping", "sourceHandle": None},
            {"id": "e2", "source": "ping", "target": "end", "sourceHandle": None},
        ],
    }
    return {
        "schema_version": 1,
        "version": "1.0.0",
        "id": "acme_flow",
        "name": "Acme flow",
        "description": "Pings Acme.",
        "connections": {CONNECTION: {"type": "acme", "name": "Acme"}},
        "draft": draft,
    }


def edited(change: Callable[[dict[str, Any]], object]) -> dict[str, Any]:
    body = flow_file()
    change(body)
    return body


def test_the_shipped_flows_are_listed_and_need_the_types_they_use() -> None:
    entries = {e.id: e for e in build_index(load_files(MARKETPLACE / "catalog")).entries}
    assert entries["slack_alert_on_severity"].requires == ["connection-type/slack"]
    assert entries["github_issue_from_report"].requires == ["connection-type/github"]
    assert entries["openai_summarize_text"].requires == ["connection-type/openai"]
    assert all(entries[f.id].has_readme for f in SHIPPED)


def test_a_flow_may_use_a_connection_type_from_the_same_snapshot(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file())
    put(tmp_path, "flows", "acme_flow", "1.0.0", flow_file())
    entries = build_index(load_files(tmp_path)).entries
    assert [(e.kind, e.requires) for e in entries] == [
        ("connection-type", []),
        ("flow", ["connection-type/acme"]),
    ]


def test_a_flow_needs_a_type_that_exists(tmp_path: Path) -> None:
    put(tmp_path, "flows", "acme_flow", "1.0.0", flow_file())
    with pytest.raises(ValueError, match="connection type 'acme' does not exist"):
        load_files(tmp_path)


def test_a_flow_may_share_an_id_with_a_template(tmp_path: Path) -> None:
    put(tmp_path, "connection-types", "acme", "1.0.0", type_file())
    put(tmp_path, "node-templates", "acme_flow", "1.0.0", template_file(id="acme_flow"))
    put(tmp_path, "flows", "acme_flow", "1.0.0", flow_file())
    assert len(load_files(tmp_path)) == 3


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (edited(lambda b: b.update(connections={})), "is used but not declared"),
        (
            edited(
                lambda b: b["connections"].update({str(uuid.uuid4()): {"type": "a", "name": "A"}})
            ),
            "is declared but no node uses it",
        ),
        (
            edited(lambda b: b.update(connections={"slot": {"type": "acme", "name": "Acme"}})),
            "must be a UUID",
        ),
        (
            edited(lambda b: b["draft"]["nodes"][1]["data"].update(method="TRACE")),
            "Input should be",
        ),
        (edited(lambda b: b["draft"]["edges"].pop()), "end"),
        (
            edited(
                lambda b: b["draft"]["nodes"][1].update(
                    type="subflow", data={"flow_id": CONNECTION, "inputs": {}}
                )
            ),
            "needs a flow of the installer",
        ),
        (edited(lambda b: b.update(id="Acme-Flow")), "id must be lowercase"),
    ],
)
def test_an_invalid_flow_file_is_refused(body: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CatalogFlow.model_validate(body)


def test_a_flow_names_its_inputs_and_outputs() -> None:
    flow = CatalogFlow.model_validate(flow_file())
    assert (flow.input_names(), flow.output_names()) == (["who"], ["ok"])


async def test_installing_a_flow_installs_its_connection_types_and_lists_it(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/catalog/flows")).json() == {"items": []}
    response = await install(client, "flow", "github_issue_from_report")
    assert response.status_code == 201
    assert [(i["kind"], i["id"]) for i in response.json()["installed"]] == [
        ("flow", "github_issue_from_report"),
        ("connection-type", "github"),
    ]

    [item] = (await client.get("/catalog/flows")).json()["items"]
    assert item["id"] == "github_issue_from_report" and item["version"] == "1.0.0"
    assert item["inputs"] == ["owner", "repo", "title", "body"]
    assert item["outputs"] == ["number", "url"]
    [(slot, hint)] = item["connections"].items()
    assert hint == {"type": "github", "name": "GitHub"}
    used = [n for n in item["draft"]["nodes"] if n["type"] == "http_request"]
    assert [n["data"]["connection_id"] for n in used] == [slot]
    assert parse_graph(item["draft"])[1] == []

    assert (await client.get("/catalog/flows", headers=OTHER)).json() == {"items": []}


async def test_a_type_cannot_be_removed_while_an_installed_flow_needs_it(
    client: httpx.AsyncClient,
) -> None:
    await install(client, "flow", "github_issue_from_report")
    blocked = await client.delete("/catalog/installed/connection-type/github")
    assert blocked.status_code == 409 and blocked.json()["code"] == "required_by"
    assert "Open a GitHub issue from a report" in blocked.json()["message"]

    removed = await client.delete("/catalog/installed/flow/github_issue_from_report")
    assert removed.status_code == 204
    assert (await client.get("/catalog/flows")).json() == {"items": []}
    assert (await client.delete("/catalog/installed/connection-type/github")).status_code == 204


def shipped(flow_id: str) -> dict[str, Any]:
    path = MARKETPLACE / "catalog" / "flows" / flow_id / "1.0.0.json"
    return json.loads(path.read_text(encoding="utf-8"))["draft"]


async def run_slack_flow(severity: str) -> Any:
    draft = shipped("slack_alert_on_severity")
    post = next(n for n in draft["nodes"] if n["id"] == "post")
    post.update(type="assign", data={"assignments": [{"variable": "status", "value": "posting"}]})
    graph, issues = parse_graph(draft)
    assert issues == [], issues
    inputs = {"severity": severity, "channel": "#ops", "message": "disk is full"}
    return await run_flow(compile_graph(graph), inputs, None)


async def test_the_slack_flow_posts_only_for_high_severity() -> None:
    sent = await run_slack_flow("high")
    skipped = await run_slack_flow("low")
    assert sent.output == {"status": "sent"}
    assert skipped.output == {"status": "skipped"}


def test_the_summary_is_read_from_the_first_choice() -> None:
    draft = shipped("openai_summarize_text")
    end = next(n for n in draft["nodes"] if n["id"] == "end")
    value = end["data"]["outputs"][0]["value"]
    answer = {"choices": [{"message": {"content": "Short."}}]}
    assert render(value, {"nodes": {"summarize": {"output": {"body": answer}}}}) == "Short."
