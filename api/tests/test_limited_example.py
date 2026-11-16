from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.limits import Limits
from app.security.policy import outbound_policy
from app.security.ssrf import OutboundError, OutboundPolicy, fetch
from app.settings import Settings

EXAMPLE = Path(__file__).resolve().parents[2] / ".env.limited.example"

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, Limits]:
    for name, value in dotenv_values(EXAMPLE).items():
        if value is not None:
            monkeypatch.setenv(name, value)
    return Settings(_env_file=None), Limits(_env_file=None)


def test_the_demo_example_keeps_outbound_calls_to_public_https_with_small_caps(
    demo: tuple[Settings, Limits],
) -> None:
    policy = outbound_policy(*demo)

    assert policy.allow_private is False
    assert (policy.max_bytes, policy.timeout_seconds) == (1_048_576, 10)
    assert policy.allowed_hosts == ("jsonplaceholder.typicode.com", "api.github.com")


def test_the_demo_example_keeps_the_node_off_until_it_has_been_reviewed(
    demo: tuple[Settings, Limits],
) -> None:
    assert "http_request" in demo[1].disabled_node_types


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://localhost/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",
        "https://0.0.0.0/",
        "https://10.0.0.1/",
        "https://192.168.1.1/",
        "https://172.16.0.1/",
        "https://100.64.0.1/",
        "https://169.254.169.254/latest/meta-data/",
        "http://example.com/",
        "ftp://example.com/",
        "file:///etc/passwd",
    ],
)
@pytest.mark.parametrize("with_allow_list", [True, False])
async def test_the_demo_policy_refuses_every_internal_or_non_https_target(
    demo: tuple[Settings, Limits], url: str, with_allow_list: bool
) -> None:
    policy: OutboundPolicy = outbound_policy(*demo)
    if not with_allow_list:
        policy = policy.model_copy(update={"allowed_hosts": ()})

    with pytest.raises(OutboundError) as error:
        await fetch(policy, "GET", url)

    refusals = {"blocked_destination", "scheme_not_allowed", "invalid_url"}
    assert error.value.code in (refusals | {"host_not_allowed"} if with_allow_list else refusals)


async def test_the_demo_allow_list_refuses_a_public_host_that_is_not_on_it(
    demo: tuple[Settings, Limits],
) -> None:
    with pytest.raises(OutboundError) as error:
        await fetch(outbound_policy(*demo), "GET", "https://example.com/")

    assert error.value.code == "host_not_allowed"
