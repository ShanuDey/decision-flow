import { getFlow, getVersion, listFlows } from "@/lib/api/client";
import { call } from "@/lib/call";
import { type FlowContract, contractOf, type PublishedFlow } from "@/lib/graph/subflow";
import type { Graph } from "@/lib/graph/types";

import { useEditor } from "./store";

const PAGE_SIZE = 100;

// The first page by name; a workspace with more flows than that cannot pick the rest yet.
export async function loadPublishedFlows(): Promise<PublishedFlow[]> {
  const result = await call(listFlows({ sort: "name", page_size: PAGE_SIZE }));
  if (!result.ok) return [];
  return result.data.items.flatMap((f) =>
    f.published_version === null ? [] : [{ id: f.id, name: f.name, version: f.published_version }],
  );
}

export async function loadContract(flowId: string): Promise<FlowContract | null> {
  const flow = await call(getFlow(flowId));
  if (!flow.ok || flow.data.published_version === null) return null;
  const version = await call(getVersion(flowId, flow.data.published_version));
  return version.ok ? contractOf(version.data.graph as unknown as Graph) : null;
}

// Reads each flow once; an id already in the store (even a failed one) is not asked again.
export async function ensureContracts(flowIds: string[]): Promise<void> {
  const known = useEditor.getState().contracts;
  const wanted = flowIds.filter((id) => !(id in known));
  await Promise.all(
    wanted.map(async (id) => {
      const contract = await loadContract(id);
      useEditor.getState().setContract(id, contract);
    }),
  );
}
