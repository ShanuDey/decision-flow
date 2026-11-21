from app.engine.base import FrozenBaseModel


class Ref(FrozenBaseModel):
    scope: str
    path: tuple[str, ...]

    def __str__(self) -> str:
        return ".".join((self.scope, *self.path))
