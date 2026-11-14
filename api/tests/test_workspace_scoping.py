import inspect

import pytest

from app.flows.store import FlowStore
from app.runs.store import RunStore

# add_run receives a Run that already carries its workspace.
EXEMPT = {("RunStore", "add_run")}


@pytest.mark.parametrize("store", [FlowStore, RunStore])
def test_every_store_method_is_scoped_to_a_member(store: type) -> None:
    methods = [
        (name, fn)
        for name, fn in inspect.getmembers(store, inspect.iscoroutinefunction)
        if not name.startswith("_") and (store.__name__, name) not in EXEMPT
    ]
    assert methods
    for name, fn in methods:
        params = list(inspect.signature(fn).parameters)
        assert params[1] == "member", f"{store.__name__}.{name} must take `member` first"
