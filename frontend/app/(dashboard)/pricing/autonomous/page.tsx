"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Bot } from "lucide-react";

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

const AGENT_CONFIG = {
  scout: {
    icon: "🔍",
    label: "Scout Agent",
    color: "text-blue-500",
    bg: "bg-blue-500/5",
    border: "border-blue-500/30",
    description: "Market surveillance & signal detection",
    thinkingLevel: "minimal",
  },
  analyst: {
    icon: "📊",
    label: "Analyst Agent",
    color: "text-amber-500",
    bg: "bg-amber-500/5",
    border: "border-amber-500/30",
    description: "Sentiment analysis & risk assessment",
    thinkingLevel: "medium",
  },
  strategist: {
    icon: "💰",
    label: "Strategist Agent",
    color: "text-emerald-500",
    bg: "bg-emerald-500/5",
    border: "border-emerald-500/30",
    description: "Price optimization & on-chain execution",
    thinkingLevel: "high",
  },
  execution: {
    icon: "⛓️",
    label: "On-Chain Execution",
    color: "text-purple-500",
    bg: "bg-purple-500/5",
    border: "border-purple-500/30",
    description: "BNB Chain smart contract write",
    thinkingLevel: "n/a",
  },
  pipeline: {
    icon: "✅",
    label: "Pipeline",
    color: "text-emerald-500",
    bg: "bg-emerald-500/5",
    border: "border-emerald-500/30",
    description: "Complete",
    thinkingLevel: "n/a",
  },
  error: {
    icon: "❌",
    label: "Error",
    color: "text-destructive",
    bg: "bg-destructive/5",
    border: "border-destructive/30",
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

function AgentEventCard({ event }: { event: AgentEvent }) {
  const config =
    AGENT_CONFIG[event.agent as keyof typeof AGENT_CONFIG] || AGENT_CONFIG.pipeline;

  let parsedContent: Record<string, string> | null = null;
  try {
    parsedContent = JSON.parse(event.content);
  } catch {
    // plain text
  }

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{config.icon}</span>
        <span className={`font-semibold text-sm ${config.color}`}>{config.label}</span>
        {config.thinkingLevel !== "n/a" && (
          <span className="text-xs text-muted-foreground ml-auto">
            thinking: {config.thinkingLevel}
          </span>
        )}
        {event.is_complete && (
          <span className="text-xs bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 px-2 py-0.5 rounded-full ml-auto">
            Complete
          </span>
        )}
      </div>

      {parsedContent ? (
        <div className="grid grid-cols-2 gap-2 mt-2">
          {Object.entries(parsedContent).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="text-muted-foreground">{key.replace(/_/g, " ")}:</span>{" "}
              <span className="font-mono">{String(value)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{event.content}</p>
      )}

      <div className="text-xs text-muted-foreground/50 mt-2">
        {new Date(event.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

function PulsingDot({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
    </span>
  );
}

export default function AutonomousPipelinePage() {
  const [config, setConfig] = useState<PipelineConfig>(DEFAULT_CONFIG);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<PipelineStatus>("idle");
  const [elapsed, setElapsed] = useState(0);
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

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
    setEvents([]);
    setStatus("running");
    setElapsed(0);

    if (eventSourceRef.current) eventSourceRef.current.close();

    const params = new URLSearchParams({
      current_price: config.current_price.toString(),
      product_category: config.product_category,
      cost_basis: config.cost_basis.toString(),
      margin_floor_pct: config.margin_floor_pct.toString(),
    });

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${baseUrl}/api/v1/autonomous/stream/${config.product_id}?${params}`;
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
        // ignore malformed
      }
    };

    es.onerror = () => {
      setStatus("error");
      es.close();
    };
  }, [config]);

  const stopPipeline = useCallback(() => {
    if (eventSourceRef.current) eventSourceRef.current.close();
    setStatus("idle");
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Autonomous Pipeline</h1>
            <p className="text-sm text-muted-foreground">
              Zero human intervention — AI agents run 24/7 on a schedule
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <PulsingDot active={status === "running"} />
          <span
            className={`text-sm font-mono px-3 py-1 rounded-full border ${
              status === "idle"
                ? "bg-muted text-muted-foreground border-border"
                : status === "running"
                ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/30"
                : status === "complete"
                ? "bg-blue-500/10 text-blue-600 border-blue-500/30"
                : "bg-destructive/10 text-destructive border-destructive/30"
            }`}
          >
            {status === "running" ? `${(elapsed / 1000).toFixed(1)}s` : status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Configuration */}
        <div className="lg:col-span-1 space-y-4">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="font-semibold mb-4 text-sm">⚙️ Pipeline Configuration</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Product ID</label>
                <input
                  type="text"
                  value={config.product_id}
                  onChange={(e) => setConfig((c) => ({ ...c, product_id: e.target.value }))}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Current Price ($)</label>
                <input
                  type="number"
                  step="0.01"
                  value={config.current_price}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, current_price: parseFloat(e.target.value) || 0 }))
                  }
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Category</label>
                <select
                  value={config.product_category}
                  onChange={(e) => setConfig((c) => ({ ...c, product_category: e.target.value }))}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
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
                  <label className="text-xs text-muted-foreground block mb-1">Cost Basis ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={config.cost_basis}
                    onChange={(e) =>
                      setConfig((c) => ({ ...c, cost_basis: parseFloat(e.target.value) || 0 }))
                    }
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Margin Floor (%)</label>
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
                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
            </div>

            <div className="mt-5">
              {status !== "running" ? (
                <button
                  onClick={runPipeline}
                  className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
                >
                  🚀 Run Autonomous Pipeline
                </button>
              ) : (
                <button
                  onClick={stopPipeline}
                  className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
                >
                  ⏹️ Stop Pipeline
                </button>
              )}
            </div>
          </div>

          {/* Architecture */}
          <div className="rounded-lg border bg-card p-4">
            <h3 className="text-sm font-semibold text-muted-foreground mb-3">
              Pipeline Architecture
            </h3>
            <div className="space-y-2 text-xs">
              {(["scout", "analyst", "strategist"] as const).map((agent) => {
                const cfg = AGENT_CONFIG[agent];
                const isActive =
                  status === "running" &&
                  events.length > 0 &&
                  events[events.length - 1]?.agent === agent;
                return (
                  <div
                    key={agent}
                    className={`flex items-center gap-2 p-2 rounded border ${
                      isActive
                        ? `${cfg.bg} ${cfg.border}`
                        : "bg-muted/30 border-transparent"
                    }`}
                  >
                    <span>{cfg.icon}</span>
                    <div className="flex-1">
                      <div className={`font-medium ${isActive ? cfg.color : "text-muted-foreground"}`}>
                        {cfg.label}
                      </div>
                      <div className="text-muted-foreground/60">{cfg.description}</div>
                    </div>
                    <div className="text-muted-foreground/40">
                      {cfg.thinkingLevel}
                    </div>
                  </div>
                );
              })}
              <div className="flex items-center gap-2 p-2 rounded bg-muted/30 border border-transparent">
                <span>⛓️</span>
                <div className="flex-1">
                  <div className="font-medium text-muted-foreground">BNB Chain</div>
                  <div className="text-muted-foreground/60">On-chain execution</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Agent Stream */}
        <div className="lg:col-span-2">
          <div className="rounded-lg border bg-card p-4 min-h-96 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-sm flex items-center gap-2">
                📡 Agent Reasoning Stream
              </h2>
              <span className="text-xs text-muted-foreground">
                {events.length} events · Real-time SSE
              </span>
            </div>

            {events.length === 0 && status === "idle" ? (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <div className="text-4xl mb-3">🤖</div>
                  <p className="text-base font-medium">No human prompting required</p>
                  <p className="text-sm mt-1 text-muted-foreground">
                    Click &quot;Run Autonomous Pipeline&quot; to trigger the agents.
                    <br />
                    In production, this runs on a schedule — 24/7, zero intervention.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 max-h-150">
                {events.map((event, i) => (
                  <AgentEventCard key={`${event.agent}-${event.phase}-${i}`} event={event} />
                ))}

                {status === "running" && (
                  <div className="flex items-center gap-2 text-muted-foreground text-sm p-3">
                    <div className="animate-spin h-4 w-4 border-2 border-muted border-t-primary rounded-full" />
                    Agent reasoning in progress...
                  </div>
                )}
                <div ref={eventsEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}



