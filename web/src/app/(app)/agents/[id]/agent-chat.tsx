"use client";

import { Plus, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { createThread, deleteThread, getThread } from "@/lib/api/client";
import type { MessageInfo, ThreadSummary, ToolCallInfo } from "@/lib/api/models";
import { errorToast } from "@/lib/api-error";
import { streamTurn } from "@/lib/agent-stream";
import { stepSummary } from "@/lib/agents";
import { call } from "@/lib/call";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const TITLE_CHARS = 60;

function Steps({ steps }: { steps: ToolCallInfo[] }) {
  if (steps.length === 0) return null;
  return (
    <ul className="flex flex-col gap-1.5">
      {steps.map((step, i) => (
        <li key={i}>
          <details className="rounded-lg border bg-background text-xs">
            <summary className="cursor-pointer px-2.5 py-1.5 font-mono">
              <span className={cn(step.is_error && "text-red-700 dark:text-red-400")}>
                {step.is_error ? "Failed: " : "Ran "}
                {stepSummary(step)}
              </span>
            </summary>
            <pre className="overflow-x-auto whitespace-pre-wrap break-words border-t px-2.5 py-2 text-muted-foreground">
              {step.result}
            </pre>
          </details>
        </li>
      ))}
    </ul>
  );
}

function Bubble({ message }: { message: MessageInfo }) {
  const mine = message.role === "user";
  return (
    <div className={cn("flex flex-col gap-1.5", mine ? "items-end" : "items-start")}>
      {!mine && message.steps && <Steps steps={message.steps} />}
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm",
          mine ? "bg-primary text-primary-foreground" : "border bg-card",
        )}
      >
        {message.content}
      </div>
      {!mine && message.usage?.total_tokens !== undefined && (
        <span className="text-[11px] text-muted-foreground">{message.usage.total_tokens} tokens</span>
      )}
    </div>
  );
}

export function AgentChat({
  agentId,
  problem,
  initialThreads,
  onOpenSettings,
}: {
  agentId: string;
  // Why the agent cannot answer yet, or null.
  problem: string | null;
  initialThreads: ThreadSummary[];
  onOpenSettings: () => void;
}) {
  const [threads, setThreads] = useState(initialThreads);
  const [activeId, setActiveId] = useState<string | null>(initialThreads[0]?.id ?? null);
  const [messages, setMessages] = useState<MessageInfo[]>([]);
  const [loading, setLoading] = useState(initialThreads.length > 0);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<{ content: string; steps: ToolCallInfo[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const open = useCallback(
    async (id: string) => {
      setActiveId(id);
      setLoading(true);
      setError(null);
      setConfirming(null);
      const result = await call(getThread(agentId, id));
      if (!result.ok) {
        errorToast("Could not load the conversation", result.error);
        setMessages([]);
      } else {
        setMessages(result.data.messages);
      }
      setLoading(false);
    },
    [agentId],
  );

  useEffect(() => {
    const first = initialThreads[0];
    if (first) {
      void call(getThread(agentId, first.id)).then((result) => {
        if (result.ok) setMessages(result.data.messages);
        else errorToast("Could not load the conversation", result.error);
        setLoading(false);
      });
    }
    const controller = abort;
    return () => controller.current?.abort();
    // only the first conversation is opened on arrival
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, pending]);

  async function start(): Promise<string | null> {
    const result = await call(createThread(agentId));
    if (!result.ok) {
      errorToast("Could not start a conversation", result.error);
      return null;
    }
    setThreads((all) => [result.data, ...all]);
    setActiveId(result.data.id);
    setMessages([]);
    return result.data.id;
  }

  async function newConversation() {
    if (pending) return;
    setError(null);
    await start();
  }

  async function send() {
    const content = draft.trim();
    if (!content || pending || problem) return;
    setError(null);
    const threadId = activeId ?? (await start());
    if (!threadId) return;
    setDraft("");
    setPending({ content, steps: [] });
    const controller = new AbortController();
    abort.current = controller;
    const outcome = await streamTurn(
      agentId,
      threadId,
      content,
      (step) => setPending((p) => (p ? { ...p, steps: [...p.steps, step] } : p)),
      controller.signal,
    );
    if (controller.signal.aborted) return;
    setPending(null);
    if (!outcome.ok) {
      setError(outcome.error.message);
      setDraft(content);
      return;
    }
    setMessages((all) => [...all, outcome.turn.user_message, outcome.turn.reply]);
    setThreads((all) =>
      all
        .map((t) => (t.id === threadId ? { ...t, title: t.title || content.slice(0, TITLE_CHARS) } : t))
        .sort((a, b) => (a.id === threadId ? -1 : b.id === threadId ? 1 : 0)),
    );
  }

  async function remove(id: string) {
    if (confirming !== id) {
      setConfirming(id);
      return;
    }
    const result = await call(deleteThread(agentId, id));
    if (!result.ok) {
      errorToast("Could not delete the conversation", result.error);
      return;
    }
    setConfirming(null);
    const left = threads.filter((t) => t.id !== id);
    setThreads(left);
    toast.success("Conversation deleted");
    if (activeId === id) {
      if (left[0]) void open(left[0].id);
      else {
        setActiveId(null);
        setMessages([]);
      }
    }
  }

  return (
    <div className="grid h-[calc(100vh-15rem)] min-h-[420px] gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col gap-2" aria-label="Conversations">
        <Button variant="outline" className="h-10 justify-start" onClick={() => void newConversation()}>
          <Plus aria-hidden /> New conversation
        </Button>
        <ul className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
          {threads.length === 0 && <li className="px-2 py-1 text-xs text-muted-foreground">No conversations yet.</li>}
          {threads.map((thread) => (
            <li key={thread.id} className="group flex items-center gap-1">
              <button
                type="button"
                aria-current={thread.id === activeId ? "true" : undefined}
                onClick={() => void open(thread.id)}
                className={cn(
                  "min-w-0 flex-1 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-muted",
                  thread.id === activeId && "bg-muted",
                )}
              >
                <span className="block truncate">{thread.title || "New conversation"}</span>
                <span className="block text-[11px] text-muted-foreground">{formatDateTime(thread.updated_at)}</span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                aria-label={confirming === thread.id ? "Confirm delete" : "Delete conversation"}
                className={cn(confirming === thread.id && "text-red-700 dark:text-red-400")}
                onClick={() => void remove(thread.id)}
              >
                {confirming === thread.id ? "Delete?" : <Trash2 aria-hidden />}
              </Button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-h-0 flex-col rounded-xl border" aria-label="Conversation">
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          {problem && (
            <p role="alert" className="rounded-lg border border-red-600/40 p-3 text-sm">
              {problem}
            </p>
          )}
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!loading && messages.length === 0 && !pending && !problem && (
            <p className="m-auto max-w-sm text-center text-sm text-muted-foreground">
              Ask the agent something. It can run the flows you gave it as tools.
            </p>
          )}
          {messages.map((m) => (
            <Bubble key={m.id} message={m} />
          ))}
          {pending && (
            <>
              <div className="flex flex-col items-end gap-1.5">
                <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl bg-primary px-3.5 py-2 text-sm text-primary-foreground">
                  {pending.content}
                </div>
              </div>
              <div className="flex flex-col items-start gap-1.5" aria-live="polite">
                <Steps steps={pending.steps} />
                <span className="text-xs text-muted-foreground">
                  {pending.steps.length === 0 ? "Thinking…" : "Working…"}
                </span>
              </div>
            </>
          )}
          {error && (
            <p role="alert" className="rounded-lg border border-red-600/40 p-3 text-sm">
              {error}
            </p>
          )}
          <div ref={end} />
        </div>
        <form
          className="flex items-end gap-2 border-t p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <Textarea
            aria-label="Message"
            rows={2}
            value={draft}
            disabled={pending !== null}
            placeholder={problem ? "Finish the settings first" : "Message the agent (Enter to send, Shift+Enter for a new line)"}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <Button type="submit" className="h-10" disabled={!draft.trim() || pending !== null || problem !== null}>
            <Send aria-hidden /> Send
          </Button>
        </form>
        {problem && (
          <p className="px-4 pb-3 text-xs text-muted-foreground">
            <button type="button" onClick={onOpenSettings} className="underline underline-offset-2">
              Open settings
            </button>
          </p>
        )}
      </section>
    </div>
  );
}
