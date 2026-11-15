from pathlib import Path

import pytest

from app.limits import Limits
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
KNOWN = {n.upper() for n in (*Limits.model_fields, *Settings.model_fields)}
# Read by the web app, Docker or Postgres, not by the API settings.
NOT_API = {
    "POSTGRES_PASSWORD",
    "API_URL",
    "AUTH_SIGNING_KEY",
    "AUTH_METHODS",
    "AUTH_AUTO_MIGRATE",
    "AUTH_ADMIN_EMAIL",
    "AUTH_ADMIN_PASSWORD",
    "AUTH_TRUSTED_ORIGINS",
    "AUTH_IP_HEADER",
    "AUTH_TRUSTED_PROXIES",
    "AUTH_TOKEN_ISSUER",
}
FILES = [ROOT / ".env.example", ROOT / ".env.limited.example"]


def keys(path: Path) -> list[str]:
    """Names set on a line, or commented out as `# NAME=value`."""
    found = []
    for raw in path.read_text().splitlines():
        name = raw.strip().lstrip("# ").split("=", 1)[0]
        if "=" in raw and name.isupper() and name.replace("_", "").isalnum():
            found.append(name)
    return found


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_api_setting_in_an_env_file_is_real(path: Path) -> None:
    api_names = [k for k in keys(path) if k not in NOT_API and not k.startswith("BETTER_")]
    assert [k for k in api_names if k not in KNOWN] == []


def test_env_example_lists_what_you_must_set() -> None:
    assert {"POSTGRES_PASSWORD", "DATABASE_URL", "CORS_ORIGINS"} <= set(keys(FILES[0]))


def test_the_demo_preset_tightens_the_defaults() -> None:
    path = FILES[1]
    fields = {k.lower() for k in keys(path)} & set(Limits.model_fields)
    assert fields, "the demo preset sets no limits"
