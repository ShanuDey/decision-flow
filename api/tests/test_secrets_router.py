from collections.abc import Iterator

import httpx
import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.limits import Limits, get_limits
from app.main import app
from app.secrets.crypto import SecretBox, get_box
from app.settings import Settings, get_settings
from tests.auth_helpers import bearer
from tests.conftest import FakeSecretStore

pytestmark = pytest.mark.anyio

VALUE = "sk_live_1234567890"


@pytest.fixture
def box() -> Iterator[SecretBox]:
    secret_box = SecretBox([Fernet.generate_key().decode()])
    app.dependency_overrides[get_box] = lambda: secret_box
    yield secret_box
    app.dependency_overrides.pop(get_box, None)


async def test_put_then_list_never_returns_the_value(
    client: httpx.AsyncClient, box: SecretBox
) -> None:
    put = await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})
    assert put.status_code == 200
    assert set(put.json()) == {"name", "created_at", "updated_at"}

    listed = await client.get("/secrets")
    assert [s["name"] for s in listed.json()["items"]] == ["STRIPE_KEY"]
    assert VALUE not in listed.text and VALUE not in put.text


async def test_the_value_is_stored_encrypted(
    client: httpx.AsyncClient, box: SecretBox, secret_store: FakeSecretStore
) -> None:
    await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})

    (stored,) = secret_store.secrets.values()
    assert VALUE not in stored.value_encrypted
    assert box.decrypt(stored.value_encrypted) == VALUE


async def test_putting_again_replaces_the_value(
    client: httpx.AsyncClient, box: SecretBox, secret_store: FakeSecretStore
) -> None:
    await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})
    await client.put("/secrets/STRIPE_KEY", json={"value": "another-value-99"})

    (stored,) = secret_store.secrets.values()
    assert box.decrypt(stored.value_encrypted) == "another-value-99"


async def test_delete_then_missing(client: httpx.AsyncClient, box: SecretBox) -> None:
    await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})

    assert (await client.delete("/secrets/STRIPE_KEY")).status_code == 204
    assert (await client.get("/secrets")).json()["items"] == []
    again = await client.delete("/secrets/STRIPE_KEY")
    assert again.status_code == 404
    assert again.json()["code"] == "not_found"


@pytest.mark.parametrize("name", ["stripe_key", "Stripe_Key", "1KEY", "_KEY", "MY-KEY", "A" * 65])
async def test_bad_names_are_rejected(client: httpx.AsyncClient, box: SecretBox, name: str) -> None:
    response = await client.put(f"/secrets/{name}", json={"value": VALUE})
    assert response.status_code == 422


async def test_the_longest_and_shortest_names_are_accepted(
    client: httpx.AsyncClient, box: SecretBox
) -> None:
    assert (await client.put("/secrets/A", json={"value": VALUE})).status_code == 200
    assert (await client.put(f"/secrets/{'A' * 64}", json={"value": VALUE})).status_code == 200


@pytest.mark.parametrize("value", ["", "short", "1234567"])
async def test_short_values_are_rejected(
    client: httpx.AsyncClient, box: SecretBox, value: str
) -> None:
    response = await client.put("/secrets/STRIPE_KEY", json={"value": value})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


async def test_a_value_is_kept_exactly(
    client: httpx.AsyncClient, box: SecretBox, secret_store: FakeSecretStore
) -> None:
    padded = "  spaced value  "
    await client.put("/secrets/STRIPE_KEY", json={"value": padded})

    (stored,) = secret_store.secrets.values()
    assert box.decrypt(stored.value_encrypted) == padded


async def test_another_workspace_sees_nothing(client: httpx.AsyncClient, box: SecretBox) -> None:
    await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})
    other = bearer(sub="someone-else")

    assert (await client.get("/secrets", headers=other)).json()["items"] == []
    assert (await client.delete("/secrets/STRIPE_KEY", headers=other)).status_code == 404
    assert len((await client.get("/secrets")).json()["items"]) == 1


async def test_same_name_in_two_workspaces_is_two_secrets(
    client: httpx.AsyncClient, box: SecretBox, secret_store: FakeSecretStore
) -> None:
    other = bearer(sub="someone-else")
    await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})
    await client.put("/secrets/STRIPE_KEY", json={"value": "different-value-1"}, headers=other)

    assert len(secret_store.secrets) == 2


async def test_without_a_session_it_is_401(anon_client: httpx.AsyncClient) -> None:
    assert (await anon_client.get("/secrets")).status_code == 401
    assert (await anon_client.put("/secrets/KEY", json={"value": VALUE})).status_code == 401
    assert (await anon_client.delete("/secrets/KEY")).status_code == 401


@pytest.fixture
def small_cap() -> Iterator[None]:
    app.dependency_overrides[get_limits] = lambda: Limits(
        _env_file=None, max_secrets_per_workspace=1
    )
    yield
    app.dependency_overrides.pop(get_limits, None)


@pytest.mark.usefixtures("small_cap")
async def test_the_cap_blocks_a_new_name_but_not_a_replace(
    client: httpx.AsyncClient, box: SecretBox
) -> None:
    assert (await client.put("/secrets/ONE_KEY", json={"value": VALUE})).status_code == 200

    replace = await client.put("/secrets/ONE_KEY", json={"value": "new-value-12345"})
    assert replace.status_code == 200
    blocked = await client.put("/secrets/TWO_KEY", json={"value": VALUE})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "secret_limit_reached"

    await client.delete("/secrets/ONE_KEY")
    assert (await client.put("/secrets/TWO_KEY", json={"value": VALUE})).status_code == 200


async def test_saving_needs_an_encryption_key(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, encryption_key="")
    try:
        response = await client.put("/secrets/STRIPE_KEY", json={"value": VALUE})
        listed = await client.get("/secrets")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert response.json()["code"] == "secrets_not_configured"
    assert listed.status_code == 200


def test_encrypt_round_trip_and_a_wrong_key_fails() -> None:
    box = SecretBox([Fernet.generate_key().decode()])
    token = box.encrypt(VALUE)

    assert token != VALUE and box.decrypt(token) == VALUE
    with pytest.raises(InvalidToken):
        SecretBox([Fernet.generate_key().decode()]).decrypt(token)


def test_a_rotated_key_still_reads_old_values() -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    token = SecretBox([old]).encrypt(VALUE)

    rotated = SecretBox([new, old])
    assert rotated.decrypt(token) == VALUE
    assert SecretBox([new]).decrypt(rotated.encrypt(VALUE)) == VALUE


def test_settings_reject_a_malformed_key_without_echoing_it() -> None:
    with pytest.raises(ValueError, match="Fernet") as error:
        Settings(_env_file=None, encryption_key="not-a-key-at-all")
    assert "not-a-key-at-all" not in str(error.value)


def test_settings_accept_several_keys() -> None:
    first, second = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    settings = Settings(_env_file=None, encryption_key=f"{first}, {second}")
    assert settings.encryption_keys == [first, second]
