class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.node_inputs: dict[str, dict] = {}
        self.node_outputs: dict[str, object] = {}
        self.run_inputs: dict | None = None
        self.run_outputs: dict | None = None

    async def run_started(self, inputs) -> None:
        self.run_inputs = inputs
        self.events.append(("run_started",))

    async def node_started(self, node, inputs) -> None:
        self.node_inputs[node.id] = inputs
        self.events.append(("started", node.id))

    async def node_finished(self, node, status, duration_ms, error, outputs=None) -> None:
        assert duration_ms >= 0
        self.node_outputs[node.id] = outputs
        self.events.append(("finished", node.id, status, error))

    async def run_finished(self, status, error, outputs=None) -> None:
        self.run_outputs = outputs
        self.events.append(("run_finished", status, error))
