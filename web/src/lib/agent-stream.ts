import { type ApiErrorBody, parseEvents } from "@/lib/agents";
import type { ToolCallInfo, TurnResponse } from "@/lib/api/models";

export type TurnOutcome = { ok: true; turn: TurnResponse } | { ok: false; error: ApiErrorBody };

const LOST: ApiErrorBody = { code: "network_error", message: "Cannot reach the API" };
const CUT: ApiErrorBody = { code: "stream_ended", message: "The connection ended before the agent answered" };

// Sends one message and reports each flow the agent runs while it works.
export async function streamTurn(
  agentId: string,
  threadId: string,
  content: string,
  onTool: (step: ToolCallInfo) => void,
  signal?: AbortSignal,
): Promise<TurnOutcome> {
  let response: Response;
  try {
    response = await fetch(`/backend/agents/${agentId}/threads/${threadId}/messages/stream`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify({ content }),
      signal,
    });
  } catch {
    return { ok: false, error: LOST };
  }
  if (!response.ok || !response.body) {
    const body = (await response.json().catch(() => null)) as Partial<ApiErrorBody> | null;
    return {
      ok: false,
      error: {
        code: body?.code ?? "http_error",
        message: body?.message ?? `Request failed (${response.status})`,
      },
    };
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const parsed = parseEvents(done ? `${buffer}\n\n` : buffer);
      buffer = parsed.rest;
      for (const event of parsed.events) {
        if (event.type === "tool") onTool(event.step);
        else if (event.type === "message") return { ok: true, turn: event.turn };
        else return { ok: false, error: event.error };
      }
      if (done) return { ok: false, error: CUT };
    }
  } catch {
    return { ok: false, error: signal?.aborted ? CUT : LOST };
  }
}
