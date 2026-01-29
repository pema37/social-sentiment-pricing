"use client";

import React, { useRef, useEffect } from "react";
import { AgentMessage, AgentKey } from "../types";
import { AGENT_CONFIG, THOUGHT_LABELS } from "../constants";

interface AgentStreamProps {
  messages: AgentMessage[];
  activeAgent: string | null;
}

export function AgentStream({ messages, activeAgent }: AgentStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  if (messages.length === 0 && !activeAgent) {
    return null;
  }

  // Group messages by agent
  const groupedMessages = messages.reduce((acc, msg) => {
    if (!acc[msg.agent]) acc[msg.agent] = [];
    acc[msg.agent].push(msg);
    return acc;
  }, {} as Record<string, AgentMessage[]>);

  const agentOrder: AgentKey[] = ["scout", "analyst", "strategist"];

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900/50 overflow-hidden">
      <div className="border-b border-gray-700 bg-gray-800/50 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">Agent Analysis</h3>
          {activeAgent && (
            <span className="text-sm text-gray-400">Processing...</span>
          )}
        </div>
      </div>

      <div ref={containerRef} className="max-h-96 overflow-y-auto p-4 space-y-4">
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
                <span className="text-xs text-gray-500">
                  {isActive && "Processing..."}
                  {isComplete && "Complete"}
                </span>
              </div>

              <div className="space-y-2">
                {agentMessages.map((msg, idx) => (
                  <div key={idx} className="text-sm">
                    {msg.thought_type && (
                      <span className="text-xs text-gray-500 mr-2 uppercase">
                        [{THOUGHT_LABELS[msg.thought_type] || msg.thought_type}]
                      </span>
                    )}
                    <span className={msg.is_final ? "text-white" : "text-gray-300"}>
                      {msg.content}
                    </span>
                  </div>
                ))}
                {isActive && agentMessages.length === 0 && (
                  <p className="text-sm text-gray-400 italic">{config.description}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


