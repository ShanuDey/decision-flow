import { afterEach, describe, expect, it, vi } from "vitest";

import { streamTurn } from "./agent-stream";

function reply(chunks: string[], init: ResponseInit = {}): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, init);
}

const TOOL = 'event: tool\ndata: {"name":"a","arguments":{},"result":"1","is_error":false}\n\n';
const MESSAGE = 'event: message\ndata: {"user_message":{"content":"hi"},"reply":{"content":"yo"}}\n\n';

afterEach(() => vi.unstubAllGlobals());

describe("streamTurn", () => {
  it("passes the answer text on piece by piece before the final message", async () => {
    const token = (index: number, text: string) => `event: token\ndata: {"index": ${index}, "text": "${text}"}\n\n`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply([token(1, "Hel"), token(1, "lo"), MESSAGE])));
    const pieces: [number, string][] = [];
    const outcome = await streamTurn("a", "t", "hi", {
      onTool: () => {},
      onToken: (index, text) => pieces.push([index, text]),
    });
    expect(pieces).toEqual([
      [1, "Hel"],
      [1, "lo"],
    ]);
    expect(outcome.ok && outcome.turn.reply.content).toBe("yo");
  });

  it("reports tools as they arrive, even split across chunks, then returns the answer", async () => {
    const half = Math.floor(MESSAGE.length / 2);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply([TOOL.slice(0, 10), TOOL.slice(10), MESSAGE.slice(0, half), MESSAGE.slice(half)])));
    const seen: string[] = [];
    const outcome = await streamTurn("a", "t", "hi", { onTool: (s) => seen.push(s.name) });
    expect(seen).toEqual(["a"]);
    expect(outcome.ok && outcome.turn.reply.content).toBe("yo");
  });

  it("returns an error event as an error", async () => {
    const error = 'event: error\ndata: {"code":"agent_stopped","message":"too long"}\n\n';
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply([error])));
    expect(await streamTurn("a", "t", "hi", { onTool: () => {} })).toEqual({
      ok: false,
      error: { code: "agent_stopped", message: "too long" },
    });
  });

  it("reads the error body of a refused request", async () => {
    const refused = new Response(JSON.stringify({ code: "not_found", message: "Thread not found" }), { status: 404 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(refused));
    expect(await streamTurn("a", "t", "hi", { onTool: () => {} })).toEqual({
      ok: false,
      error: { code: "not_found", message: "Thread not found" },
    });
  });

  it("says so when the stream ends without an answer or the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply([TOOL])));
    const cut = await streamTurn("a", "t", "hi", { onTool: () => {} });
    expect(!cut.ok && cut.error.code).toBe("stream_ended");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    const lost = await streamTurn("a", "t", "hi", { onTool: () => {} });
    expect(!lost.ok && lost.error.code).toBe("network_error");
  });
});
