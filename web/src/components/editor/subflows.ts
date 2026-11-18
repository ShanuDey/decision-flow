import { getFlow, getVersion, listFlows } from "@/lib/api/client";
import { call } from "@/lib/call";
import { contractOf, type FlowContract, type PublishedPage, publishedPage } from "@/lib/graph/subflow";
import type { Graph } from "@/lib/graph/types";

import { useEditor } from "./store";

export const PAGE_SIZE = 100;

// One page by name; `more` says the picker's search is needed to reach the rest. Null: it failed.
export async function loadPublishedFlows(query?: string): Promise<PublishedPage | null> {
  const result = await call(listFlows({ sort: "name", page_size: PAGE_SIZE, q: query || undefined }));
  return result.ok ? publishedPage(result.data.items, result.data.total) : null;
}

export async function loadContract(flowId: string): Promise<FlowContract | null> {
  const flow = await call(getFlow(flowId));
  if (!flow.ok || flow.data.published_version === null) return null;
  const version = await call(getVersion(flowId, flow.data.published_version));
  if (!version.ok) return null;
  const { id, name, published_version } = flow.data;
  useEditor.getState().addPublishedFlow({ id, name, version: published_version });
  return contractOf(version.data.graph as unknown as Graph);
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
