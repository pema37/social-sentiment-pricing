"use client";

import { useState, useRef } from "react";
import { API_BASE, CRISIS_AGENTS, THOUGHT_LABELS } from "./constants";
import type { CrisisAgent, StreamEvent } from "./types";

interface AgentOutput {
  agent: CrisisAgent;
  content: string;
  thoughtType?: string;
}

export default function CrisisDetectorDemo() {
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
      const url = `${API_BASE}/crisis/analyze/stream?product=${encodeURIComponent(product)}&simulate_crisis=${simulateCrisis}`;
      const response = await fetch(url, { signal: abortRef.current.signal });
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
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-bold">Crisis Detector</h1>
          <a
            href="/demo"
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            ← Back to Demo Hub
          </a>
        </div>
        <p className="text-gray-400 mb-8">AI-powered sentiment crisis monitoring</p>

        {/* Controls */}
        <div className="bg-gray-900 rounded-lg p-6 mb-8">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-50">
              <label className="block text-sm text-gray-400 mb-2">Product Name</label>
              <input
                type="text"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                disabled={isRunning}
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={simulateCrisis}
                onChange={(e) => setSimulateCrisis(e.target.checked)}
                disabled={isRunning}
                className="w-4 h-4"
              />
              <span className="text-sm text-gray-400">Simulate Crisis</span>
            </label>
            <button
              onClick={isRunning ? stopAnalysis : runAnalysis}
              className={`px-6 py-2 rounded font-medium ${
                isRunning
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {isRunning ? "Stop" : "Run Analysis"}
            </button>
          </div>
        </div>

        {/* Agent Cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {(Object.keys(CRISIS_AGENTS) as CrisisAgent[]).map((key) => {
            const agent = CRISIS_AGENTS[key];
            const isActive = activeAgent === key;
            return (
              <div
                key={key}
                className={`p-4 rounded-lg border-2 transition-all ${
                  isActive
                    ? `${agent.borderActive} ${agent.bgActive}`
                    : "border-gray-800 bg-gray-900"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{agent.name}</span>
                  {isActive && (
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-500">{agent.description}</div>
              </div>
            );
          })}
        </div>

        {/* Output Stream */}
        <div className="bg-gray-900 rounded-lg p-6 min-h-100">
          <h2 className="text-lg font-semibold mb-4">Analysis Stream</h2>
          {outputs.length === 0 ? (
            <p className="text-gray-500">Run analysis to see agent thinking...</p>
          ) : (
            <div className="space-y-2 font-mono text-sm">
              {outputs.map((o, i) => {
                const agentInfo = CRISIS_AGENTS[o.agent];
                const thought = o.thoughtType ? THOUGHT_LABELS[o.thoughtType] : null;
                return (
                  <div key={i} className="flex gap-2">
                    <span className={`${agentInfo.labelColor} font-semibold shrink-0`}>
                      [{agentInfo.name.split(" ")[0]}]
                    </span>
                    {thought && (
                      <span className={`${thought.color} shrink-0`}>[{thought.label}]</span>
                    )}
                    <span className="text-gray-300">{o.content}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-sm text-gray-500">
          <p>GetActualPrice.com | Google Gemini API Developer Competition • February 2026</p>
        </div>
      </div>
    </div>
  );
}


