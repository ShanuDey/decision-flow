from typing import get_args

import pytest

from app.engine.nodes import NODE_TYPES, Node, NodeModel


def test_registry_and_the_parsing_union_list_the_same_types() -> None:
    union = {t for t in get_args(get_args(Node)[0])}
    assert union == set(NODE_TYPES)


@pytest.mark.parametrize("cls", NODE_TYPES, ids=lambda c: c.__name__)
def test_every_node_type_is_a_node_with_a_name_and_a_handler(cls: type[NodeModel]) -> None:
    assert issubclass(cls, NodeModel)
    assert cls.type_name() == cls.model_fields["type"].annotation.__args__[0]
    assert "run" in vars(cls)  # overrides the base, which raises NotImplementedError


def test_type_traits() -> None:
    by_name = {c.type_name(): c for c in NODE_TYPES}
    start, end = by_name["start"], by_name["end"]
    assert (start.min_count, start.max_count, start.accepts_incoming) == (1, 1, False)
    assert (end.min_count, end.max_count, end.accepts_outgoing) == (1, None, False)
    assign = by_name["assign"]
    assert (assign.min_count, assign.max_count) == (0, None)
    assert (assign.accepts_incoming, assign.accepts_outgoing) == (True, True)
    condition = by_name["condition"]
    assert (condition.min_count, condition.max_count) == (0, None)
    assert condition.handles == ("true", "false")
    assert assign.handles == ()
