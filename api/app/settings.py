from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    database_url: str = "postgresql+psycopg://decisionflow:decisionflow@localhost:5432/decisionflow"

    # Largest accepted request body (flow drafts are the biggest legitimate payload).
    max_request_bytes: int = 1_048_576

    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_set_experiment: str = "decision-flow"

    # NoDecode: accept comma-separated env values instead of JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
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
