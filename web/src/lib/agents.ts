import type { AgentUpdate, ToolCallInfo, TurnResponse } from "@/lib/api/models";

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

export interface ApiErrorBody {
  code: string;
  message: string;
}

export type AgentEvent =
  | { type: "tool"; step: ToolCallInfo }
  | { type: "message"; turn: TurnResponse }
  | { type: "error"; error: ApiErrorBody };

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

function parseBlock(block: string): AgentEvent | null {
  let name = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!name || data.length === 0) return null;
  let body: unknown;
  try {
    body = JSON.parse(data.join("\n"));
  } catch {
    return null;
  }
  if (name === "tool") return { type: "tool", step: body as ToolCallInfo };
  if (name === "message") return { type: "message", turn: body as TurnResponse };
  if (name === "error") return { type: "error", error: body as ApiErrorBody };
  return null;
}

// Takes the text received so far; returns the events that are complete and the rest.
export function parseEvents(buffer: string): { events: AgentEvent[]; rest: string } {
  const parts = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts.flatMap((block) => {
    const event = parseBlock(block);
    return event ? [event] : [];
  });
  return { events, rest };
}

export function stepSummary(step: ToolCallInfo): string {
  const args = Object.entries(step.arguments)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(", ");
  return args ? `${step.name}(${args})` : step.name;
}
