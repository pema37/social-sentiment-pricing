"use client";

import { useState, useRef } from "react";
import { ShieldAlert } from "lucide-react";
import {
  CRISIS_AGENTS,
  THOUGHT_LABELS,
} from "@/components/features/alerts/crisis/constants";
import type {
  CrisisAgent,
  StreamEvent,
} from "@/components/features/alerts/crisis/types";

interface AgentOutput {
  agent: CrisisAgent;
  content: string;
  thoughtType?: string;
}

export default function CrisisDetectorPage() {
  const [product, setProduct] = useState("iPhone 15 Pro");
  const [simulateCrisis, setSimulateCrisis] = useState(false);
  const [outputs, setOutputs] = useState<AgentOutput[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [activeAgent, setActiveAgent] = useState<CrisisAgent | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const runAnalysis = async () => {
    setIsRunning(true);
    setOutputs([]);
    abortRef.current = new AbortController();

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const url = `${baseUrl}/api/v1/crisis/analyze/stream?product=${encodeURIComponent(product)}&simulate_crisis=${simulateCrisis}`;

      const response = await fetch(url, {
        credentials: "include",
        signal: abortRef.current.signal,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader");

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event: StreamEvent = JSON.parse(line.slice(6));
            if (event.done) break;
            if (event.error) throw new Error(event.error);

            if (event.agent && event.content) {
              setActiveAgent(event.agent);
              setOutputs((prev) => [
                ...prev,
                {
                  agent: event.agent!,
                  content: event.content!,
                  thoughtType: event.thought_type || undefined,
                },
              ]);
            }
          } catch (e) {
            if (e instanceof SyntaxError) {
              console.error("SSE parse error:", e);
            } else {
              throw e;
            }
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        console.error("Analysis failed:", e);
      }
    } finally {
      setIsRunning(false);
      setActiveAgent(null);
    }
  };

  const stopAnalysis = () => {
    abortRef.current?.abort();
    setIsRunning(false);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
          <ShieldAlert className="h-5 w-5 text-destructive" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Crisis Detector</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered sentiment crisis monitoring for your products
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium mb-2">Product Name</label>
            <input
              type="text"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              className="w-full rounded-lg border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              disabled={isRunning}
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer pb-1">
            <input
              type="checkbox"
              checked={simulateCrisis}
              onChange={(e) => setSimulateCrisis(e.target.checked)}
              disabled={isRunning}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm text-muted-foreground">Simulate Crisis</span>
          </label>
          <button
            onClick={isRunning ? stopAnalysis : runAnalysis}
            className={`px-6 py-2 rounded-lg text-sm font-medium transition-colors ${
              isRunning
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            }`}
          >
            {isRunning ? "Stop" : "Run Analysis"}
          </button>
        </div>
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-3 gap-4">
        {(Object.keys(CRISIS_AGENTS) as CrisisAgent[]).map((key) => {
          const agent = CRISIS_AGENTS[key];
          const isActive = activeAgent === key;
          return (
            <div
              key={key}
              className={`p-4 rounded-lg border-2 transition-all ${
                isActive
                  ? `${agent.borderActive} ${agent.bgActive}`
                  : "border-border bg-card"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{agent.name}</span>
                {isActive && (
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
                  </span>
                )}
              </div>
              <div className="text-sm text-muted-foreground">{agent.description}</div>
            </div>
          );
        })}
      </div>

      {/* Output Stream */}
      <div className="rounded-lg border bg-card p-6 min-h-48">
        <h2 className="text-base font-semibold mb-4">Analysis Stream</h2>
        {outputs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Run analysis to see agent thinking...
          </p>
        ) : (
          <div className="space-y-2 font-mono text-sm max-h-96 overflow-y-auto">
            {outputs.map((o, i) => {
              const agentInfo = CRISIS_AGENTS[o.agent];
              const thought = o.thoughtType
                ? THOUGHT_LABELS[o.thoughtType]
                : null;
              return (
                <div key={i} className="flex gap-2">
                  <span
                    className={`${agentInfo?.labelColor || "text-muted-foreground"} font-semibold shrink-0`}
                  >
                    [{agentInfo?.name.split(" ")[0] || o.agent}]
                  </span>
                  {thought && (
                    <span className={`${thought.color} shrink-0`}>
                      [{thought.label}]
                    </span>
                  )}
                  <span className="text-muted-foreground">{o.content}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}



