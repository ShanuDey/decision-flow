import type { AgentUpdate, ThreadSummary } from "@/lib/api/models";
import { parseApiDate } from "@/lib/format";

export interface ToolForm {
  flow_id: string;
  name: string;
  description: string;
}

export interface AgentForm {
  name: string;
  description: string;
  connection_id: string;
  model: string;
  instructions: string;
  tools: ToolForm[];
  max_iterations: number;
  max_total_tokens: number | null;
  max_seconds: number | null;
  temperature: number | null;
  max_tokens: number | null;
  timeout_seconds: number | null;
}

// The whole form is sent, so a cleared limit becomes null and the API clears it.
export function updateBody(form: AgentForm): AgentUpdate {
  return {
    name: form.name.trim(),
    description: form.description,
    connection_id: form.connection_id || null,
    model: form.model.trim(),
    instructions: form.instructions,
    tools: form.tools,
    max_iterations: form.max_iterations,
    max_total_tokens: form.max_total_tokens,
    max_seconds: form.max_seconds,
    temperature: form.temperature,
    max_tokens: form.max_tokens,
    timeout_seconds: form.timeout_seconds,
  };
}

// "Agent", then "Agent 2", "Agent 3"... the first that no other agent has.
export function uniqueName(stem: string, existing: string[]): string {
  const taken = new Set(existing.map((n) => n.trim().toLowerCase()));
  let name = stem;
  for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${stem} ${n}`;
  return name;
}

export function sameForm(a: AgentForm, b: AgentForm): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// The first thing that stops the form from being saved, or null.
export function formProblem(form: AgentForm): string | null {
  if (!form.name.trim()) return "Give the agent a name";
  const names = new Set<string>();
  for (const [i, tool] of form.tools.entries()) {
    const label = `Tool ${i + 1}`;
    if (!tool.flow_id) return `${label}: pick a flow`;
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(tool.name)) return `${label}: use 1 to 64 letters, digits, _ or -`;
    if (names.has(tool.name)) return `${label}: another tool is named ${tool.name}`;
    names.add(tool.name);
    if (!tool.description.trim()) return `${label}: say what it does and when to use it`;
  }
  return null;
}

// What a tool was called with, short enough for one line: "income 45000 · credit_score 720".
export function argsSummary(args: Record<string, unknown> | undefined): string {
  return Object.entries(args ?? {})
    .map(([key, value]) => `${key} ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" · ");
}

export function whoLabel(thread: Pick<ThreadSummary, "source" | "external_user_id" | "anonymous">): string | null {
  if (thread.source !== "api") return null;
  const id = thread.external_user_id ?? "";
  return thread.anonymous ? `Anonymous · ${id.replace(/^anon-/, "").slice(0, 6)}` : `External · ${id}`;
}

export interface ThreadGroup {
  label: "Today" | "Yesterday" | "Earlier";
  items: ThreadSummary[];
}

function dayStart(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

// The conversation list by the day each was last active, in the viewer's time zone, newest first.
export function groupByDay(threads: ThreadSummary[], now: Date = new Date()): ThreadGroup[] {
  const today = dayStart(now);
  const day = 24 * 60 * 60 * 1000;
  const buckets: Record<ThreadGroup["label"], ThreadSummary[]> = { Today: [], Yesterday: [], Earlier: [] };
  for (const thread of threads) {
    const started = dayStart(parseApiDate(thread.updated_at));
    buckets[started >= today ? "Today" : started >= today - day ? "Yesterday" : "Earlier"].push(thread);
  }
  return (["Today", "Yesterday", "Earlier"] as const)
    .filter((label) => buckets[label].length > 0)
    .map((label) => ({ label, items: buckets[label] }));
}
