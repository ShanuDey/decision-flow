"""Shared bases for engine models."""

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
