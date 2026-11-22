"use client";

import { ChevronDown, Plus } from "lucide-react";
import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import { toast } from "sonner";

import { TraceDialog } from "@/components/trace/trace-dialog";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { createThread, deleteThread, getMessageSteps } from "@/lib/api/client";
import type { ThreadSummary } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import { parseApiDate } from "@/lib/format";

import { AgentRuntime, type StoredTurn } from "./agent-runtime";
import { AgentThread } from "./agent-thread";
import { ThreadList } from "./thread-list";

const TITLE_CHARS = 60;

// On narrow screens the list folds into a menu above the chat.
function ThreadPicker({
  threads,
  activeId,
  onOpen,
  onDelete,
}: {
  threads: ThreadSummary[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const active = threads.find((t) => t.id === activeId);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger className="inline-flex h-9 max-w-[min(20rem,60vw)] items-center gap-2 rounded-lg bg-muted/60 px-3 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50">
        <span className="truncate">{active ? active.title || "New chat" : "Conversations"}</span>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      </PopoverTrigger>
      <PopoverContent className="w-80 p-2">
        <ThreadList
          threads={threads}
          activeId={activeId}
          className="max-h-96"
          onOpen={(id) => {
            onOpen(id);
            setOpen(false);
          }}
          onDelete={onDelete}
        />
      </PopoverContent>
    </Popover>
  );
}

// The agent's conversations on the left and the open one on the right, ready for the next message.
export function AgentChats({
  agentId,
  agentName,
  problem,
  threads,
  setThreads,
  activeId,
  setActiveId,
}: {
  agentId: string;
  agentName: string;
  // Why the agent cannot answer yet, or null.
  problem: string | null;
  threads: ThreadSummary[];
  setThreads: Dispatch<SetStateAction<ThreadSummary[]>>;
  activeId: string | null;
  setActiveId: (id: string | null) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const active = threads.find((t) => t.id === activeId);

  async function newConversation() {
    setError(null);
    const result = await call(createThread(agentId));
    if (!result.ok) {
      errorToast("Could not start a conversation", result.error);
      return;
    }
    setThreads((all) => [result.data, ...all]);
    setActiveId(result.data.id);
  }

  // A turn was stored: the first message names the conversation and it moves to the top.
  const stored = useCallback(
    (threadId: string, turn: StoredTurn) => {
      const title = turn.user_message.content.slice(0, TITLE_CHARS);
      setThreads((all) =>
        all
          .map((t) => (t.id === threadId ? { ...t, title: t.title || title } : t))
          .sort((a, b) => (a.id === threadId ? -1 : b.id === threadId ? 1 : 0)),
      );
    },
    [setThreads],
  );

  async function remove(id: string) {
    const result = await call(deleteThread(agentId, id));
    if (!result.ok) {
      errorToast("Could not delete the conversation", result.error);
      return;
    }
    const left = threads.filter((t) => t.id !== id);
    setThreads(left);
    toast.success("Conversation deleted");
    if (activeId === id) setActiveId(left[0]?.id ?? null);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)] xl:h-[calc(100dvh-8rem)] xl:min-h-[520px]">
      <aside aria-label="Conversations" className="hidden min-h-0 flex-col gap-3 rounded-xl border bg-card p-3 lg:flex">
        <Button variant="outline" className="h-10 justify-start gap-2" onClick={() => void newConversation()}>
          <Plus aria-hidden /> New chat
        </Button>
        <ThreadList threads={threads} activeId={activeId} onOpen={setActiveId} onDelete={remove} className="flex-1" />
      </aside>

      <section aria-label="Conversation" className="flex h-[75dvh] min-h-0 min-w-0 flex-col rounded-xl border xl:h-auto">
        <div className="flex items-center gap-2 border-b px-4 py-2.5">
          <div className="lg:hidden">
            <ThreadPicker threads={threads} activeId={activeId} onOpen={setActiveId} onDelete={remove} />
          </div>
          <div className="hidden min-w-0 lg:block">
            <h2 className="truncate font-semibold">{active ? active.title || "New chat" : agentName}</h2>
            {active && (
              <p className="text-xs text-muted-foreground">Started {parseApiDate(active.created_at).toLocaleString()}</p>
            )}
          </div>
          <Button variant="ghost" className="ml-auto h-9 gap-1.5 lg:hidden" onClick={() => void newConversation()}>
            <Plus aria-hidden /> New
          </Button>
        </div>
        {problem && (
          <div role="alert" className="mx-4 mt-3 rounded-xl border border-red-600/40 p-3 text-sm">
            {problem}
          </div>
        )}
        {activeId ? (
          <AgentRuntime
            key={activeId}
            agentId={agentId}
            threadId={activeId}
            onStored={(turn) => stored(activeId, turn)}
            onError={setError}
          >
            <AgentThread agentName={agentName} problem={problem} onTrace={setTraceId} />
          </AgentRuntime>
        ) : (
          <div className="m-auto flex max-w-sm flex-col items-center gap-3 p-6 text-center">
            <h2 className="text-lg font-semibold">Ask {agentName} something</h2>
            <p className="text-sm text-muted-foreground">
              Start a chat. The agent can run the flows you gave it as tools.
            </p>
            <Button className="h-10" onClick={() => void newConversation()}>
              <Plus aria-hidden /> New chat
            </Button>
          </div>
        )}
        {error && (
          <p role="alert" className="mx-4 mb-3 rounded-xl border border-red-600/40 p-3 text-sm">
            {error}
          </p>
        )}
      </section>

      {traceId && activeId && (
        <TraceDialog
          open
          onOpenChange={(open) => !open && setTraceId(null)}
          title={active?.title || "New chat"}
          runId={traceId}
          fetchSteps={(id) => call(getMessageSteps(agentId, activeId, id))}
        />
      )}
    </div>
  );
}
