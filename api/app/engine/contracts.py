from app.engine.fields import TypedField
from app.engine.graph import Graph
from app.engine.nodes import EndNode, StartNode
from app.engine.run_secrets import referenced_connection_ids, referenced_secret_names
from app.engine.subflow import FlowContract


def contract_of(graph: Graph) -> FlowContract:
    start = next((n for n in graph.nodes if isinstance(n, StartNode)), None)
    end = next((n for n in graph.nodes if isinstance(n, EndNode)), None)
    calls = {flow_id for n in graph.nodes for flow_id in n.called_flow_ids()}
    return FlowContract(
        inputs=start.data.inputs if start else [],
        outputs=[TypedField(name=o.name, type=o.type, values=o.values) for o in end.data.outputs]
        if end
        else [],
        calls=sorted(calls),
        secret_names=sorted(referenced_secret_names(graph)),
        connection_ids=sorted(referenced_connection_ids(graph)),
    )
