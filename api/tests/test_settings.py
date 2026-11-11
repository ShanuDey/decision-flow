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


@pytest.fixture
def no_mlflow_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.mark.usefixtures("no_mlflow_env")
def test_mlflow_tracking_uri_is_derived_from_the_app_database() -> None:
    s = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@db.test:5432/app")
    assert s.mlflow_tracking_uri == (
        "postgresql+psycopg://u:p@db.test:5432/app?options=-csearch_path%3Dmlflow"
    )


@pytest.mark.usefixtures("no_mlflow_env")
def test_derived_mlflow_tracking_uri_keeps_the_other_query_parameters() -> None:
    s = Settings(
        _env_file=None, database_url="postgresql+psycopg://u:p@db.test/app?sslmode=require"
    )
    assert "sslmode=require" in s.mlflow_tracking_uri
    assert "options=-csearch_path%3Dmlflow" in s.mlflow_tracking_uri


@pytest.mark.usefixtures("no_mlflow_env")
def test_derived_mlflow_tracking_uri_adds_to_existing_options() -> None:
    s = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@db.test/app?options=-cstatement_timeout%3D5000",
    )
    assert s.mlflow_tracking_uri.endswith(
        "options=-cstatement_timeout%3D5000+-csearch_path%3Dmlflow"
    )


@pytest.mark.usefixtures("no_mlflow_env")
def test_derived_mlflow_tracking_uri_joins_a_repeated_options_parameter() -> None:
    s = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@db.test/app?options=-ca%3D1&options=-cb%3D2",
    )
    assert s.mlflow_tracking_uri.endswith("options=-ca%3D1+-cb%3D2+-csearch_path%3Dmlflow")


def test_mlflow_tracking_uri_set_explicitly_is_used_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")
    assert Settings(_env_file=None).mlflow_tracking_uri == "http://mlflow.test:5000"


def test_empty_mlflow_tracking_uri_means_derive_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "")
    assert "search_path%3Dmlflow" in Settings(_env_file=None).mlflow_tracking_uri


def test_mlflow_experiment_default_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MLFLOW_SET_EXPERIMENT", raising=False)
    assert Settings(_env_file=None).mlflow_set_experiment == "decision-flow"
    monkeypatch.setenv("MLFLOW_SET_EXPERIMENT", "my-exp")
    assert Settings(_env_file=None).mlflow_set_experiment == "my-exp"
