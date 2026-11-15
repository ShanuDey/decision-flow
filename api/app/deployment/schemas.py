from typing import Literal

from app.engine.base import FrozenBaseModel


class AppConfig(FrozenBaseModel):
    delete_mode: Literal["hard", "soft"]
