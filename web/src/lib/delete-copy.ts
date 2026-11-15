export type DeleteMode = "hard" | "soft";

export function deleteCopy(mode: DeleteMode, name: string): string {
  return mode === "soft"
    ? `\u201c${name}\u201d will be removed from your flows. Its versions and runs are kept for audit.`
    : `This deletes \u201c${name}\u201d, its published versions and all of its runs. It cannot be undone.`;
}
