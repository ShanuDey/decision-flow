import type { CallToolResult } from "@modelcontextprotocol/server";

export const MAX_RESULT_CHARS = 100_000;
const MAX_LISTED_ISSUES = 10;

const text = (value: string): CallToolResult["content"] => [{ type: "text", text: value }];

export function failure(message: string): CallToolResult {
  return { isError: true, content: text(message) };
}

export function truncate(value: string): string {
  if (value.length <= MAX_RESULT_CHARS) return value;
  const code = value.charCodeAt(MAX_RESULT_CHARS - 1);
  const end = code >= 0xd800 && code <= 0xdbff ? MAX_RESULT_CHARS - 1 : MAX_RESULT_CHARS;
  const dropped = value.length - end;
  return `${value.slice(0, end)}\n... truncated, ${dropped} more characters. Ask for less (a smaller page or limit, or one flow).`;
}

interface Issue {
  message?: unknown;
  node_id?: unknown;
  field?: unknown;
}

function issueLine(issue: Issue): string {
  const where = [issue.node_id, issue.field].filter((part) => typeof part === "string" && part).join(" / ");
  return `- ${where ? `${where}: ` : ""}${String(issue.message ?? "invalid")}`;
}

export function describeFailure(status: number, body: string, retryAfter: string | null): string {
  let parsed: { code?: unknown; message?: unknown; details?: Record<string, unknown> } | null = null;
  try {
    parsed = JSON.parse(body);
  } catch {
    parsed = null;
  }
  if (!parsed || typeof parsed.message !== "string") {
    return `Request failed (HTTP ${status}).`;
  }

  const code = typeof parsed.code === "string" ? parsed.code : `http_${status}`;
  const lines = [`${code}: ${parsed.message}`];
  const details = parsed.details ?? {};

  if (Array.isArray(details.errors) && details.errors.length > 0) {
    const issues = details.errors as Issue[];
    lines.push(...issues.slice(0, MAX_LISTED_ISSUES).map(issueLine));
    if (issues.length > MAX_LISTED_ISSUES) lines.push(`- ...and ${issues.length - MAX_LISTED_ISSUES} more`);
  }
  if (code === "draft_conflict" && details.draft_version !== undefined) {
    lines.push(`The current draft_version is ${String(details.draft_version)}. Call get_flow, then save again with that value as if_match.`);
  }
  if (code === "precondition_required") {
    lines.push("Pass if_match: the draft_version returned by get_flow.");
  }
  if (retryAfter && Number.isFinite(Number(retryAfter))) {
    lines.push(`Retry after about ${retryAfter} seconds.`);
  }
  return lines.join("\n");
}

export async function resultOf(response: Response): Promise<CallToolResult> {
  const body = await response.text();
  if (!response.ok) {
    return failure(describeFailure(response.status, body, response.headers.get("retry-after")));
  }
  return { content: text(truncate(body === "" ? "Done." : body)) };
}
