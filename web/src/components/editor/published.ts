export interface PublishedInfo {
  version: number;
  draftVersion: number;
}

export function publishedInfo(flow: {
  published_version: number | null;
  published_draft_version: number | null;
}): PublishedInfo | null {
  if (flow.published_version === null || flow.published_draft_version === null) return null;
  return { version: flow.published_version, draftVersion: flow.published_draft_version };
}

export function keepNote(keepLatest: number): string | null {
  if (keepLatest <= 0) return null;
  return `Only the newest ${keepLatest} version${keepLatest === 1 ? " is" : "s are"} kept. Older ones are deleted when you publish.`;
}
