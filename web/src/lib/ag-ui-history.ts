import type { MessageInfo } from "@/lib/api/models";

// The messages the chat library loads for a conversation, in AG-UI's message shape. The runtime
// joins an assistant turn's calls and answer into one message, which keeps the id of the record
// that carries the answer: the id of the message we stored.
export type HistoryMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      toolCalls?: { id: string; type: "function"; function: { name: string; arguments: string } }[];
    }
  | { id: string; role: "tool"; content: string; toolCallId: string };

export function historyToAgUi(messages: MessageInfo[]): HistoryMessage[] {
  return messages.flatMap((message): HistoryMessage[] => {
    if (message.role === "user") return [{ id: message.id, role: "user", content: message.content }];
    const steps = message.steps ?? [];
    const answer: HistoryMessage = { id: message.id, role: "assistant", content: message.content };
    if (steps.length === 0) return [answer];
    const ids = steps.map((_, i) => `${message.id}:t${i + 1}`);
    return [
      {
        id: `${message.id}:calls`,
        role: "assistant",
        content: "",
        toolCalls: steps.map((step, i) => ({
          id: ids[i],
          type: "function",
          function: { name: step.name, arguments: JSON.stringify(step.arguments) },
        })),
      },
      ...steps.map((step, i): HistoryMessage => ({
        id: `${ids[i]}:result`,
        role: "tool",
        toolCallId: ids[i],
        content: step.result,
      })),
      answer,
    ];
  });
}

// A live message is `<run id>:m<n>`, so only a bare id (or its `:calls` twin) is one we stored.
const STORED = /^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?::calls)?$/i;

// The id we stored a reply under, from the id of a loaded message; null for a live one.
export function storedMessageId(id: string): string | null {
  return STORED.exec(id)?.[1] ?? null;
}
