"use client";

import {
  ActionBarPrimitive,
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  type ToolCallMessagePartProps,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import { ArrowUp, Bot, Check, ChevronRight, Copy, ListTree, Loader2, Square, X } from "lucide-react";
import { createContext, useContext, useMemo, useState } from "react";
import remarkGfm from "remark-gfm";

import { storedMessageId } from "@/lib/ag-ui-history";
import { argsSummary } from "@/lib/agents";
import { cn } from "@/lib/utils";

import { DictationButton, DictationPreview } from "./agent-dictation";
import type { StoredTurn } from "./agent-runtime";

const Conversation = createContext<{ agentName: string; onTrace: (id: string) => void } | null>(null);

const ACTION =
  "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50";

function Avatar({ size = 24 }: { size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full border bg-muted text-muted-foreground"
      style={{ width: size, height: size }}
    >
      <Bot style={{ width: size * 0.55, height: size * 0.55 }} aria-hidden />
    </span>
  );
}

function Markdown() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      className="break-words leading-relaxed [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:text-[0.85em] [&_h1]:mt-3 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:font-semibold [&_li]:mt-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_p+p]:mt-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_table]:my-2 [&_table]:w-full [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_ul]:list-disc [&_ul]:pl-5"
    />
  );
}

function resultText(result: unknown): string {
  if (result === undefined) return "";
  return typeof result === "string" ? result : JSON.stringify(result);
}

function ToolCard({ toolName, args, result, isError, status }: ToolCallMessagePartProps) {
  const [open, setOpen] = useState(false);
  const running = status.type === "running";
  const failed = isError === true || (status.type === "incomplete" && status.reason === "error");
  return (
    <div className="w-full rounded-xl border bg-card text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {running ? (
          <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-label="Running" />
        ) : failed ? (
          <X className="size-4 shrink-0 text-red-600 dark:text-red-400" aria-label="Failed" />
        ) : (
          <Check className="size-4 shrink-0 text-green-600 dark:text-green-400" aria-label="Done" />
        )}
        <span className="font-medium">{toolName}</span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-muted-foreground">
          {running ? "running…" : argsSummary(args)}
        </span>
        <ChevronRight
          className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")}
          aria-hidden
        />
      </button>
      {open && (
        <div className="flex flex-col gap-2 border-t px-3 py-2.5 text-xs">
          <div>
            <div className="mb-1 text-muted-foreground">Arguments</div>
            <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono">
              {JSON.stringify(args ?? {}, null, 2)}
            </pre>
          </div>
          {!running && (
            <div>
              <div className="mb-1 text-muted-foreground">{failed ? "Error" : "Result"}</div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono">{resultText(result)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Messages loaded from our history carry the id they were stored under; a live one learns it from
// the `message.stored` event, which arrives as a data part.
function storedFrom(id: string, content: readonly unknown[]): { id: string; tokens?: number } | null {
  for (const part of content) {
    const p = part as { type?: string; name?: string; data?: StoredTurn };
    if (p.type === "data" && p.name === "message.stored" && p.data) {
      return { id: p.data.reply.id, tokens: p.data.reply.usage?.total_tokens };
    }
  }
  const loaded = storedMessageId(id);
  return loaded ? { id: loaded } : null;
}

function useStored() {
  // Selected one value at a time: a selector that builds a new object each call loops forever.
  const messageId = useAuiState((s) => s.message.id);
  const content = useAuiState((s) => s.message.content);
  const stored = useMemo(() => storedFrom(messageId, content as readonly unknown[]), [messageId, content]);
  return stored;
}

function MessageFooter() {
  const conversation = useContext(Conversation);
  const stored = useStored();
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        <ActionBarPrimitive.Root hideWhenRunning className="flex items-center">
          <ActionBarPrimitive.Copy className={ACTION}>
            <AuiIf condition={(s) => s.message.isCopied}>
              <Check className="size-3.5" aria-hidden /> Copied
            </AuiIf>
            <AuiIf condition={(s) => !s.message.isCopied}>
              <Copy className="size-3.5" aria-hidden /> Copy
            </AuiIf>
          </ActionBarPrimitive.Copy>
        </ActionBarPrimitive.Root>
        {stored && (
          <button
            type="button"
            onClick={() => conversation?.onTrace(stored.id)}
            className={ACTION}
          >
            <ListTree className="size-3.5" aria-hidden /> Trace
          </button>
        )}
        {stored?.tokens !== undefined && (
          <span className="px-1.5 text-xs text-muted-foreground">{stored.tokens.toLocaleString()} tokens</span>
        )}
      </div>
    </div>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-[18px] bg-primary px-4 py-2.5 text-primary-foreground">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  const conversation = useContext(Conversation);
  return (
    <MessagePrimitive.Root className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Avatar />
        {conversation?.agentName}
      </div>
      <MessagePrimitive.Parts>
        {({ part }) => {
          if (part.type === "text") return part.text ? <Markdown /> : null;
          if (part.type === "tool-call") return part.toolUI ?? <ToolCard {...part} />;
          return null;
        }}
      </MessagePrimitive.Parts>
      <AuiIf condition={(s) => s.message.status?.type !== "running"}>
        <MessageFooter />
      </AuiIf>
    </MessagePrimitive.Root>
  );
}

function Thinking() {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
      <Loader2 className="size-4 animate-spin" aria-hidden /> Thinking…
    </div>
  );
}

export function AgentThread({
  agentName,
  problem,
  onTrace,
  readOnly = false,
}: {
  agentName: string;
  // Why the agent cannot answer yet, or null.
  problem: string | null;
  onTrace: (id: string) => void;
  // Shows the conversation without a composer.
  readOnly?: boolean;
}) {
  return (
    <Conversation.Provider value={{ agentName, onTrace }}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col items-center">
        <ThreadPrimitive.Viewport className="w-full min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-[880px] flex-col gap-7 px-2 py-4">
            <AuiIf condition={(s) => s.thread.isLoading}>
              <p className="text-sm text-muted-foreground">Loading…</p>
            </AuiIf>
            <AuiIf condition={(s) => s.thread.isEmpty && !s.thread.isLoading && problem === null && !readOnly}>
              <div className="flex flex-col items-center gap-3 pt-24 text-center">
                <Avatar size={44} />
                <h2 className="text-lg font-semibold">Ask {agentName} something</h2>
                <p className="max-w-sm text-sm text-muted-foreground">
                  It can run the flows you gave it as tools, and you can open each step to see what it did.
                </p>
              </div>
            </AuiIf>
            <ThreadPrimitive.Messages>
              {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
            </ThreadPrimitive.Messages>
            <AuiIf condition={(s) => s.thread.isRunning && s.thread.messages.at(-1)?.role === "user"}>
              <Thinking />
            </AuiIf>
          </div>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
      {!readOnly && (
      <div className="mx-auto flex w-full max-w-[880px] flex-col gap-2 px-2 pb-4 pt-2">
        <ComposerPrimitive.Root className="flex flex-col gap-2 rounded-[20px] border bg-card px-4 pb-2.5 pt-3.5 shadow-sm focus-within:ring-3 focus-within:ring-ring/30">
          <ComposerPrimitive.Input
            aria-label="Message"
            rows={1}
            disabled={problem !== null}
            placeholder={problem ? "Finish the settings first" : `Message ${agentName}…`}
            className="max-h-48 min-h-6 w-full resize-none bg-transparent text-sm leading-6 outline-none [field-sizing:content] placeholder:text-muted-foreground disabled:opacity-50"
          />
          <div className="flex items-center gap-2">
            <DictationPreview />
            <div className="ml-auto flex items-center gap-1.5">
              <DictationButton disabled={problem !== null} />
            <AuiIf condition={(s) => !s.thread.isRunning}>
              <ComposerPrimitive.Send
                aria-label="Send"
                disabled={problem !== null}
                className="flex size-8 items-center justify-center rounded-full bg-primary text-primary-foreground outline-none transition-opacity focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-30"
              >
                <ArrowUp className="size-4" aria-hidden />
              </ComposerPrimitive.Send>
            </AuiIf>
            <AuiIf condition={(s) => s.thread.isRunning}>
              <ComposerPrimitive.Cancel
                aria-label="Stop"
                className="flex size-8 items-center justify-center rounded-full border bg-background outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <Square className="size-3.5 fill-current" aria-hidden />
              </ComposerPrimitive.Cancel>
            </AuiIf>
            </div>
          </div>
        </ComposerPrimitive.Root>
        <p className="text-center text-xs text-muted-foreground">Enter to send · Shift+Enter for a new line</p>
      </div>
      )}
    </Conversation.Provider>
  );
}
