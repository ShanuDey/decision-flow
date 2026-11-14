from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from app.auth.config import ProviderConfig

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
MLFLOW_SCHEMA_OPTION = "-csearch_path=mlflow"


def query_options(url: URL) -> str:
    """The `options` query value; a repeated parameter arrives as a tuple."""
    value = url.query.get("options", "")
    return " ".join(value) if isinstance(value, tuple) else value


def mlflow_uri_from(database_url: str) -> str:
    """The app database with MLflow's tables routed to the `mlflow` schema."""
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return database_url
    options = " ".join(filter(None, [query_options(url), MLFLOW_SCHEMA_OPTION]))
    return url.update_query_dict({"options": options}).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    database_url: str = "postgresql+psycopg://decisionflow:decisionflow@localhost:5432/decisionflow"

    # Empty: derive from database_url (schema `mlflow`); set to send traces elsewhere.
    mlflow_tracking_uri: str = ""
    mlflow_set_experiment: str = "decision-flow"

    @model_validator(mode="after")
    def _derive_mlflow_tracking_uri(self) -> "Settings":
        if not self.mlflow_tracking_uri:
            self.mlflow_tracking_uri = mlflow_uri_from(self.database_url)
        return self

    # NoDecode: accept comma-separated env values instead of JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Auth is always on; startup fails when auth_providers is empty (docs/auth.md).
    auth_providers: list[ProviderConfig] = []
    auth_allowed_email_domains: Annotated[list[str], NoDecode] = []

    # /docs, /redoc and /openapi.json list every endpoint: opt in locally, leave off when deployed.
    api_docs_enabled: bool = False

    @field_validator("auth_providers", mode="after")
    @classmethod
    def _unique_provider_names(cls, providers: list[ProviderConfig]) -> list[ProviderConfig]:
        names = [p.name for p in providers]
        if len(set(names)) != len(names):
            raise ValueError("auth_providers names must be unique")
        return providers

    @field_validator("auth_allowed_email_domains", mode="after")
    @classmethod
    def _clean_domains(cls, domains: list[str]) -> list[str]:
        return [d.strip().lower().lstrip("@") for d in domains]

    @field_validator("cors_origins", "auth_allowed_email_domains", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [part for part in value.split(",") if part.strip()]
        return value

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _clean_origins(cls, origins: list[str]) -> list[str]:
        cleaned = [origin.strip().rstrip("/") for origin in origins]
        if "*" in cleaned:
            raise ValueError("cors_origins must list explicit origins; '*' is not allowed")
        return cleaned


@lru_cache
def get_settings() -> Settings:
    return Settings()
