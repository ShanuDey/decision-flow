"use client";

import {
  Background,
  ControlButton,
  Controls,
  Panel,
  ReactFlow,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { WandSparkles } from "lucide-react";
import { useTheme } from "next-themes";
import { useState } from "react";

import { configureNode, deleteFromCanvas, tidyCanvas } from "./actions";
import { AddNodeButton } from "./add-node-picker";
import { CanvasMenu, type MenuTarget } from "./canvas-menu";
import { LimitHint } from "./limit-hint";
import { nodeTypes } from "./node-view";
import { useEditor } from "./store";

export function Canvas() {
  const nodes = useEditor((s) => s.nodes);
  const edges = useEditor((s) => s.edges);
  const onNodesChange = useEditor((s) => s.onNodesChange);
  const onEdgesChange = useEditor((s) => s.onEdgesChange);
  const onConnect = useEditor((s) => s.onConnect);
  const isValidConnection = useEditor((s) => s.isValidConnection);
  const selectOnly = useEditor((s) => s.selectOnly);
  const { fitView } = useReactFlow();
  const { resolvedTheme } = useTheme();
  const [target, setTarget] = useState<MenuTarget | null>(null);

  return (
    <div className="h-full min-w-0 flex-1" aria-label="Flow canvas">
      <CanvasMenu target={target} onReset={() => setTarget(null)}>
        <ReactFlow
          colorMode={resolvedTheme === "dark" ? "dark" : "light"}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          isValidConnection={isValidConnection}
          deleteKeyCode={["Backspace", "Delete"]}
          // Deletes go through our store (Undo); returning false stops React Flow deleting too.
          onBeforeDelete={async ({ nodes: gone, edges: goneEdges }) => {
            deleteFromCanvas(
              gone.map((n) => n.id),
              goneEdges.map((e) => e.id),
            );
            return false;
          }}
          onNodeDoubleClick={(_, node) => configureNode(node.id)}
          onNodeContextMenu={(_, node) => {
            selectOnly(node.id);
            setTarget({ kind: "node", id: node.id });
          }}
          onEdgeContextMenu={(_, edge) => setTarget({ kind: "edge", id: edge.id })}
          fitView
          fitViewOptions={{ maxZoom: 1, padding: 0.3 }}
          proOptions={{ hideAttribution: false }}
        >
          <Background />
          <Controls showInteractive={false}>
            <ControlButton
              title="Tidy up layout"
              aria-label="Tidy up layout"
              onClick={() => {
                tidyCanvas();
                void fitView({ maxZoom: 1, padding: 0.3, duration: 200 });
              }}
            >
              <WandSparkles />
            </ControlButton>
          </Controls>
          <Panel position="top-left">
            <div className="flex items-center gap-3">
              <AddNodeButton />
              <LimitHint />
            </div>
          </Panel>
        </ReactFlow>
      </CanvasMenu>
    </div>
  );
}
