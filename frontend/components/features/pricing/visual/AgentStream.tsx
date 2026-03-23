"use client";

import React, { useRef, useEffect } from "react";
import { AgentMessage, AgentKey } from "./types";
import { AGENT_CONFIG, THOUGHT_LABELS } from "./constants";

interface AgentStreamProps {
  messages: AgentMessage[];
  activeAgent: AgentKey | null;
}

export function AgentStream({ messages, activeAgent }: AgentStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0 && !activeAgent) return null;

  const groupedMessages = messages.reduce((acc, msg) => {
    if (!acc[msg.agent]) acc[msg.agent] = [];
    acc[msg.agent].push(msg);
    return acc;
  }, {} as Record<string, AgentMessage[]>);

  const agentOrder: AgentKey[] = ["scout", "analyst", "strategist"];

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="border-b bg-muted/50 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Agent Analysis</h3>
          {activeAgent && (
            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
              </span>
              Processing...
            </span>
          )}
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto p-4 space-y-4">
        {agentOrder.map((agentKey) => {
          const config = AGENT_CONFIG[agentKey];
          const agentMessages = groupedMessages[agentKey] || [];
          const isActive = activeAgent === agentKey;
          const isComplete = agentMessages.some((m) => m.is_final);

          if (agentMessages.length === 0 && !isActive) return null;

          return (
            <div
              key={agentKey}
              className={`rounded-lg border ${config.borderColor} ${config.bgColor} p-4`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${config.bgColor} ${config.color} border ${config.borderColor}`}>
                    {config.label}
                  </span>
                  <span className={`font-medium ${config.color}`}>{config.name}</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {isActive && !isComplete && (
                    <span className="flex items-center gap-1.5">
                      <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
                      </span>
                      Processing...
                    </span>
                  )}
                  {isComplete && "✓ Complete"}
                </span>
              </div>

              <div className="space-y-2">
                {agentMessages.map((msg, idx) => (
                  <div key={idx} className="text-sm">
                    {msg.thought_type && (
                      <span className="text-xs text-muted-foreground mr-2 uppercase">
                        [{THOUGHT_LABELS[msg.thought_type] || msg.thought_type}]
                      </span>
                    )}
                    <span className={msg.is_final ? "text-foreground" : "text-muted-foreground"}>
                      {msg.content}
                    </span>
                  </div>
                ))}
                {isActive && agentMessages.length === 0 && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground italic">
                    <span className="flex gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                    {config.description}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}



