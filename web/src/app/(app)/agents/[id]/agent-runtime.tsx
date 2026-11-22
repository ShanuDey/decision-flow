"use client";

import { HttpAgent } from "@ag-ui/client";
import { AssistantRuntimeProvider, ExportedMessageRepository } from "@assistant-ui/react";
import { fromAgUiMessages, useAgUiRuntime } from "@assistant-ui/react-ag-ui";
import { useEffect, useMemo, useRef } from "react";

import { historyToAgUi } from "@/lib/ag-ui-history";
import { getThread } from "@/lib/api/client";
import type { MessageInfo } from "@/lib/api/models";
import { call } from "@/lib/call";

// What the server reports once a turn is stored: the ids the Trace toggle and the list need.
export interface StoredTurn {
  user_message: MessageInfo;
  reply: MessageInfo;
}

// One conversation: the chat library talks AG-UI to our endpoint through the same-origin proxy,
// and loads earlier messages from our own thread endpoint, because the server owns the history.
export function AgentRuntime({
  agentId,
  threadId,
  onStored,
  onError,
  children,
}: {
  agentId: string;
  threadId: string;
  onStored: (turn: StoredTurn) => void;
  onError: (message: string) => void;
  children: React.ReactNode;
}) {
  const agent = useMemo(
    () => new HttpAgent({ url: `/backend/agents/${agentId}/invoke`, threadId }),
    [agentId, threadId],
  );
  const latest = useRef({ onStored, onError });
  useEffect(() => {
    latest.current = { onStored, onError };
  });

  useEffect(() => {
    const subscription = agent.subscribe({
      onCustomEvent: ({ event }) => {
        if (event.name === "message.stored") latest.current.onStored(event.value as StoredTurn);
      },
    });
    return () => subscription.unsubscribe();
  }, [agent]);

  const adapters = useMemo(
    () => ({
      history: {
        async load() {
          const result = await call(getThread(agentId, threadId));
          if (!result.ok) throw new Error(result.error.message);
          const messages = historyToAgUi(result.data.messages);
          return ExportedMessageRepository.fromArray(
            fromAgUiMessages(messages, { joinAdjacentAssistantMessages: true }),
          );
        },
        // The server stores each turn itself.
        async append() {},
      },
    }),
    [agentId, threadId],
  );

  const runtime = useAgUiRuntime({
    agent,
    adapters,
    joinAdjacentAssistantMessages: true,
    onError: (error) => latest.current.onError(error.message),
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
