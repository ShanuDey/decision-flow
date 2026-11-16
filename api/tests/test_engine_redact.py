import json
from typing import Any, Literal
from urllib.parse import quote_plus

import pytest

from app.engine.compiler import compile_graph
from app.engine.nodes import NodeContext, NodeModel
from app.engine.redact import MASK, Redactor
from app.engine.run_secrets import RunSecrets
from app.engine.runtime import run_flow
from tests.recorder import Recorder
from tests.test_engine_secrets import graph_with

VALUE = "s3cret-value-123"


def redactor(**values: str) -> Redactor:
    return Redactor(RunSecrets(values=values))


def test_a_stored_value_is_replaced_by_its_name_anywhere_in_a_structure() -> None:
    masked = redactor(API_KEY=VALUE).apply(
        {
            "a": f"Bearer {VALUE}",
            "b": [VALUE, {"c": f"x{VALUE}y"}],
            "n": 5,
            "ok": True,
            "none": None,
        }
    )

    assert masked == {
        "a": "Bearer [REDACTED:API_KEY]",
        "b": ["[REDACTED:API_KEY]", {"c": "x[REDACTED:API_KEY]y"}],
        "n": 5,
        "ok": True,
        "none": None,
    }


def test_the_longer_value_wins_when_one_contains_the_other() -> None:
    masked = redactor(SHORT="abcdefgh", LONG="abcdefghijkl").apply("abcdefghijkl and abcdefgh")

    assert masked == "[REDACTED:LONG] and [REDACTED:SHORT]"


def test_json_escaped_and_url_encoded_forms_are_masked_too() -> None:
    tricky = 'pa"ss/wor d&1'
    masked = redactor(PASSWORD=tricky).apply(
        [json.dumps({"k": tricky}), f"https://x.test/?p={quote_plus(tricky)}"]
    )

    assert masked == [
        '{"k": "[REDACTED:PASSWORD]"}',
        "https://x.test/?p=[REDACTED:PASSWORD]",
    ]
    assert tricky not in str(masked)


@pytest.mark.parametrize(
    "name", ["Authorization", "authorization", "PROXY-AUTHORIZATION", "Cookie"]
)
def test_a_credential_header_is_hidden_even_with_no_stored_secret(name: str) -> None:
    assert Redactor().apply({name: "Bearer typed-by-hand"}) == {name: MASK}


def test_a_credential_header_holding_a_stored_secret_names_it() -> None:
    masked = redactor(API_KEY=VALUE).apply({"Authorization": f"Bearer {VALUE}"})

    assert masked == {"Authorization": "Bearer [REDACTED:API_KEY]"}


def test_headers_written_as_name_value_pairs_are_masked() -> None:
    masked = Redactor().apply(
        [{"name": "X-Api-Key", "value": "abc"}, {"name": "Accept", "value": "json"}]
    )

    assert masked == [{"name": "X-Api-Key", "value": MASK}, {"name": "Accept", "value": "json"}]


def test_a_credential_header_with_a_non_text_value_is_hidden() -> None:
    assert Redactor().apply({"Cookie": ["a=1", "b=2"], "Authorization": None}) == {
        "Cookie": MASK,
        "Authorization": None,
    }


def test_nothing_changes_without_secrets_or_credential_headers() -> None:
    payload = {"amount": 5, "tier": "silver", "headers": {"Accept": "json"}, "list": [1, "a"]}

    assert Redactor().apply(payload) == payload
    assert redactor(EMPTY="").apply("text") == "text"


class Leaky(NodeModel):
    """Misbehaves on purpose: the redactor is the safety net behind well-behaved nodes."""

    type: Literal["leaky"] = "leaky"
    how: Literal["raise", "echo", "header"] = "echo"

    async def run(self, state: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        value = ctx.secrets.as_scope()["API_KEY"]
        if self.how == "raise":
            raise ValueError(f"upstream rejected key {value}")
        output: dict[str, Any] = {"echo": f"got {value}"}
        if self.how == "header":
            output = {"headers": {"Authorization": "Bearer typed-by-hand"}}
        return {"nodes": {self.id: {"output": output}}}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def run_leaky(how: str) -> tuple[Recorder, Any]:
    recorder = Recorder()
    flow = compile_graph(graph_with(Leaky(id="leak", how=how)))  # type: ignore[arg-type]
    result = await run_flow(
        flow, {"amount": 5}, recorder, secrets=RunSecrets(values={"API_KEY": VALUE})
    )
    return recorder, result


@pytest.mark.anyio
async def test_an_error_that_quotes_a_secret_is_masked_in_the_result_and_the_observer() -> None:
    recorder, result = await run_leaky("raise")

    assert result.status == "failed" and result.error.node_id == "leak"
    assert result.error.message == "upstream rejected key [REDACTED:API_KEY]"
    assert ("finished", "leak", "failed", "upstream rejected key [REDACTED:API_KEY]") in (
        recorder.events
    )
    assert ("run_finished", "failed", "upstream rejected key [REDACTED:API_KEY]") in recorder.events
    assert VALUE not in str(vars(recorder)) + result.model_dump_json()


@pytest.mark.anyio
async def test_an_output_that_echoes_a_secret_is_masked_for_the_node_and_everything_after_it() -> (
    None
):
    recorder, result = await run_leaky("echo")

    assert result.status == "succeeded"
    assert recorder.node_outputs["leak"] == {"echo": "got [REDACTED:API_KEY]"}
    assert recorder.node_inputs["end"]["nodes"]["leak"]["output"] == {
        "echo": "got [REDACTED:API_KEY]"
    }
    assert VALUE not in str(vars(recorder)) + result.model_dump_json()


@pytest.mark.anyio
async def test_a_credential_header_in_a_node_output_is_hidden_in_the_record() -> None:
    recorder, _ = await run_leaky("header")

    assert recorder.node_outputs["leak"] == {"headers": {"Authorization": MASK}}
    assert "typed-by-hand" not in str(vars(recorder))
