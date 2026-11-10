import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_default_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000"]


def test_comma_separated_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com/")
    assert Settings(_env_file=None).cors_origins == ["http://a.com", "http://b.com"]


def test_wildcard_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_mlflow_experiment_default_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MLFLOW_SET_EXPERIMENT", raising=False)
    assert Settings(_env_file=None).mlflow_set_experiment == "decision-flow"
    monkeypatch.setenv("MLFLOW_SET_EXPERIMENT", "my-exp")
    assert Settings(_env_file=None).mlflow_set_experiment == "my-exp"
