"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AgentEvent {
  agent: string;
  phase: string;
  content: string;
  timestamp: string;
  is_complete: boolean;
  data?: Record<string, unknown>;
}

interface PipelineConfig {
  product_id: string;
  current_price: number;
  product_category: string;
  cost_basis: number;
  margin_floor_pct: number;
}

type PipelineStatus = "idle" | "running" | "complete" | "error";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AGENT_CONFIG = {
  scout: {
    icon: "🔍",
    label: "Scout Agent",
    color: "text-blue-400",
    bg: "bg-blue-950/40",
    border: "border-blue-800/50",
    description: "Market surveillance & signal detection",
    thinkingLevel: "minimal",
  },
  analyst: {
    icon: "📊",
    label: "Analyst Agent",
    color: "text-amber-400",
    bg: "bg-amber-950/40",
    border: "border-amber-800/50",
    description: "Sentiment analysis & risk assessment",
    thinkingLevel: "medium",
  },
  strategist: {
    icon: "💰",
    label: "Strategist Agent",
    color: "text-emerald-400",
    bg: "bg-emerald-950/40",
    border: "border-emerald-800/50",
    description: "Price optimization & on-chain execution",
    thinkingLevel: "high",
  },
  execution: {
    icon: "⛓️",
    label: "On-Chain Execution",
    color: "text-purple-400",
    bg: "bg-purple-950/40",
    border: "border-purple-800/50",
    description: "BNB Chain smart contract write",
    thinkingLevel: "n/a",
  },
  pipeline: {
    icon: "✅",
    label: "Pipeline",
    color: "text-green-400",
    bg: "bg-green-950/40",
    border: "border-green-800/50",
    description: "Complete",
    thinkingLevel: "n/a",
  },
  error: {
    icon: "❌",
    label: "Error",
    color: "text-red-400",
    bg: "bg-red-950/40",
    border: "border-red-800/50",
    description: "Pipeline error",
    thinkingLevel: "n/a",
  },
} as const;

const DEFAULT_CONFIG: PipelineConfig = {
  product_id: "demo-product-001",
  current_price: 99.99,
  product_category: "electronics",
  cost_basis: 45.0,
  margin_floor_pct: 20.0,
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Agent Event Card Component
// ---------------------------------------------------------------------------

function AgentEventCard({ event }: { event: AgentEvent }) {
  const config = AGENT_CONFIG[event.agent as keyof typeof AGENT_CONFIG] || AGENT_CONFIG.pipeline;

  let parsedContent: Record<string, string> | null = null;
  try {
    parsedContent = JSON.parse(event.content);
  } catch {
    // content is plain text
  }

  return (
    <div
      className={`rounded-lg border ${config.border} ${config.bg} p-4 transition-all duration-300 animate-in fade-in slide-in-from-bottom-2`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{config.icon}</span>
        <span className={`font-semibold ${config.color}`}>{config.label}</span>
        {config.thinkingLevel !== "n/a" && (
          <span className="text-xs text-zinc-500 ml-auto">
            thinking: {config.thinkingLevel}
          </span>
        )}
        {event.is_complete && (
          <span className="text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded-full ml-auto">
            Complete
          </span>
        )}
      </div>

      {parsedContent ? (
        <div className="grid grid-cols-2 gap-2 mt-2">
          {Object.entries(parsedContent).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="text-zinc-500">{key.replace(/_/g, " ")}:</span>{" "}
              <span className="text-zinc-200 font-mono">{String(value)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-zinc-300">{event.content}</p>
      )}

      <div className="text-xs text-zinc-600 mt-2">
        {new Date(event.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pulsing Indicator Component
// ---------------------------------------------------------------------------

function PulsingDot({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function AutonomousPipelinePage() {
  const [config, setConfig] = useState<PipelineConfig>(DEFAULT_CONFIG);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<PipelineStatus>("idle");
  const [elapsed, setElapsed] = useState(0);
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-scroll to latest event
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  // Timer
  useEffect(() => {
    if (status === "running") {
      const start = Date.now();
      timerRef.current = setInterval(() => {
        setElapsed(Date.now() - start);
      }, 100);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [status]);

  const runPipeline = useCallback(() => {
    // Reset state
    setEvents([]);
    setStatus("running");
    setElapsed(0);

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const params = new URLSearchParams({
      current_price: config.current_price.toString(),
      product_category: config.product_category,
      cost_basis: config.cost_basis.toString(),
      margin_floor_pct: config.margin_floor_pct.toString(),
    });

    const url = `${API_BASE}/autonomous/stream/${config.product_id}?${params}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);

        if (event.agent === "pipeline" && event.is_complete) {
          setStatus("complete");
          es.close();
        }
        if (event.agent === "error") {
          setStatus("error");
          es.close();
        }
      } catch {
        // Ignore malformed events
      }
    };

    es.onerror = () => {
      setStatus("error");
      es.close();
    };
  }, [config]);

  const stopPipeline = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setStatus("idle");
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <span className="text-2xl">🤖</span> ActualPrice — Autonomous Pipeline
            </h1>
            <p className="text-sm text-zinc-500 mt-1">
              VETROX AGENTIC 3.0 · Track 3: The Hand · Zero Human Intervention
            </p>
          </div>
          <div className="flex items-center gap-3">
            <PulsingDot active={status === "running"} />
            <span
              className={`text-sm font-mono px-3 py-1 rounded-full ${
                status === "idle"
                  ? "bg-zinc-800 text-zinc-400"
                  : status === "running"
                  ? "bg-green-900/50 text-green-400"
                  : status === "complete"
                  ? "bg-blue-900/50 text-blue-400"
                  : "bg-red-900/50 text-red-400"
              }`}
            >
              {status === "running" ? `${(elapsed / 1000).toFixed(1)}s` : status}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Configuration Panel */}
          <div className="lg:col-span-1 space-y-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <span>⚙️</span> Pipeline Configuration
              </h2>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Product ID</label>
                  <input
                    type="text"
                    value={config.product_id}
                    onChange={(e) => setConfig((c) => ({ ...c, product_id: e.target.value }))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">
                    Current Price ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={config.current_price}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, current_price: parseFloat(e.target.value) || 0 }))
                    }
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Category</label>
                  <select
                    value={config.product_category}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, product_category: e.target.value }))
                    }
                    className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
                  >
                    <option value="electronics">Electronics</option>
                    <option value="fashion">Fashion</option>
                    <option value="home_goods">Home Goods</option>
                    <option value="software">Software / SaaS</option>
                    <option value="food_beverage">Food & Beverage</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1">Cost Basis ($)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={config.cost_basis}
                      onChange={(e) =>
                        setConfig((c) => ({ ...c, cost_basis: parseFloat(e.target.value) || 0 }))
                      }
                      className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 block mb-1">Margin Floor (%)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={config.margin_floor_pct}
                      onChange={(e) =>
                        setConfig((c) => ({
                          ...c,
                          margin_floor_pct: parseFloat(e.target.value) || 0,
                        }))
                      }
                      className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="mt-5 space-y-2">
                {status !== "running" ? (
                  <button
                    onClick={runPipeline}
                    className="w-full bg-green-600 hover:bg-green-500 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <span>🚀</span> Run Autonomous Pipeline
                  </button>
                ) : (
                  <button
                    onClick={stopPipeline}
                    className="w-full bg-red-600 hover:bg-red-500 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <span>⏹️</span> Stop Pipeline
                  </button>
                )}
              </div>
            </div>

            {/* Architecture Quick View */}
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <h3 className="text-sm font-semibold text-zinc-400 mb-3">Pipeline Architecture</h3>
              <div className="space-y-2 text-xs">
                {(["scout", "analyst", "strategist"] as const).map((agent, i) => {
                  const cfg = AGENT_CONFIG[agent];
                  const isActive =
                    status === "running" &&
                    events.length > 0 &&
                    events[events.length - 1]?.agent === agent;
                  return (
                    <div
                      key={agent}
                      className={`flex items-center gap-2 p-2 rounded ${
                        isActive ? cfg.bg + " " + cfg.border + " border" : "bg-zinc-800/30"
                      }`}
                    >
                      <span>{cfg.icon}</span>
                      <div className="flex-1">
                        <div className={`font-medium ${isActive ? cfg.color : "text-zinc-400"}`}>
                          {cfg.label}
                        </div>
                        <div className="text-zinc-600">{cfg.description}</div>
                      </div>
                      <div className="text-zinc-600">thinking: {cfg.thinkingLevel}</div>
                      {i < 2 && <span className="text-zinc-700 ml-1">→</span>}
                    </div>
                  );
                })}
                <div className="flex items-center gap-2 p-2 rounded bg-zinc-800/30">
                  <span>⛓️</span>
                  <div className="flex-1">
                    <div className="font-medium text-zinc-400">BNB Chain</div>
                    <div className="text-zinc-600">On-chain execution</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Agent Reasoning Stream */}
          <div className="lg:col-span-2">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 min-h-150 flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold flex items-center gap-2">
                  <span>📡</span> Agent Reasoning Stream
                </h2>
                <span className="text-xs text-zinc-500">
                  {events.length} events · Real-time SSE
                </span>
              </div>

              {events.length === 0 && status === "idle" ? (
                <div className="flex-1 flex items-center justify-center text-zinc-600">
                  <div className="text-center">
                    <div className="text-4xl mb-3">🤖</div>
                    <p className="text-lg font-medium">
                      No human prompting required
                    </p>
                    <p className="text-sm mt-1">
                      Click &quot;Run Autonomous Pipeline&quot; to trigger the agents.
                      <br />
                      In production, this runs on a schedule — 24/7, zero intervention.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                  {events.map((event, i) => (
                    <AgentEventCard key={`${event.agent}-${event.phase}-${i}`} event={event} />
                  ))}

                  {status === "running" && (
                    <div className="flex items-center gap-2 text-zinc-500 text-sm p-3">
                      <div className="animate-spin h-4 w-4 border-2 border-zinc-600 border-t-green-400 rounded-full" />
                      Agent reasoning in progress...
                    </div>
                  )}

                  <div ref={eventsEndRef} />
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 mt-12 py-6">
        <div className="max-w-6xl mx-auto px-4 flex items-center justify-between text-xs text-zinc-600">
          <span>ActualPrice — Autonomous Dynamic Pricing for the Decentralized Economy</span>
          <span>VETROX AGENTIC 3.0 · Track 3: The Hand · Powered by Gemini 3 Flash</span>
        </div>
      </footer>
    </div>
  );
}


