"use client";

import React, { useState, useRef, useEffect } from "react";
import { Globe } from "lucide-react";
import { AGENT_CONFIG, THOUGHT_LABELS, CURRENCY_OPTIONS } from "@/components/features/analytics/market-intelligence/constants";
import type {
  AgentMessage,
  AgentKey,
  PricingRecommendation,
  SourceLink,
  AnalysisStatus,
} from "@/components/features/analytics/market-intelligence/types";

export default function MarketIntelligencePage() {
  const [productName, setProductName] = useState("");
  const [currentPrice, setCurrentPrice] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [features, setFeatures] = useState("");

  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentKey | null>(null);
  const [recommendation, setRecommendation] = useState<PricingRecommendation | null>(null);
  const [sources, setSources] = useState<SourceLink[]>([]);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const streamEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleAnalyze = async () => {
    if (!productName.trim()) {
      setError("Product name is required");
      return;
    }

    setStatus("analyzing");
    setMessages([]);
    setActiveAgent(null);
    setRecommendation(null);
    setSources([]);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const body: Record<string, unknown> = {
        product_name: productName.trim(),
      };
      if (currentPrice) body.current_price = parseFloat(currentPrice);
      if (brand.trim()) body.brand = brand.trim();
      if (category.trim()) body.category = category.trim();
      if (features.trim()) {
        body.features = features.split(",").map((f) => f.trim()).filter(Boolean);
      }

      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${baseUrl}/api/v1/market-intelligence/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || `Analysis failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.done) {
                setStatus("complete");
                setActiveAgent(null);
                continue;
              }

              if (data.error) throw new Error(data.error);

              if (data.agent) {
                setActiveAgent(data.agent as AgentKey);
                setMessages((prev) => [...prev, data as AgentMessage]);

                if (data.agent === "scout" && data.is_final && data.metadata?.sources) {
                  setSources(data.metadata.sources as SourceLink[]);
                }

                if (
                  data.agent === "strategist" &&
                  data.is_final &&
                  data.metadata?.recommendation
                ) {
                  const rec = data.metadata.recommendation;
                  setRecommendation({
                    ...rec,
                    recommended_price: Number(rec.recommended_price),
                    confidence: Number(rec.confidence),
                    price_range_low: Number(rec.price_range_low),
                    price_range_high: Number(rec.price_range_high),
                    price_change_percent: Number(rec.price_change_percent),
                    sources_used: Number(rec.sources_used || 0),
                  } as PricingRecommendation);
                }
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
      }

      setStatus("complete");
      setActiveAgent(null);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setStatus("idle");
      } else {
        setError(err instanceof Error ? err.message : "Analysis failed");
        setStatus("error");
      }
      setActiveAgent(null);
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setStatus("idle");
    setActiveAgent(null);
  };

  const handleReset = () => {
    abortRef.current?.abort();
    setProductName("");
    setCurrentPrice("");
    setBrand("");
    setCategory("");
    setFeatures("");
    setStatus("idle");
    setMessages([]);
    setActiveAgent(null);
    setRecommendation(null);
    setSources([]);
    setError(null);
  };

  const isAnalyzing = status === "analyzing";
  const canAnalyze = productName.trim() && !isAnalyzing;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Globe className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Market Intelligence</h1>
          <p className="text-sm text-muted-foreground">
            Live web search + AI multi-agent pricing analysis
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column - Input */}
        <div className="space-y-6">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="text-base font-semibold mb-4">Product Details</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Product Name <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g., Nike Air Max 90"
                  disabled={isAnalyzing}
                  className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Current Price</label>
                  <input
                    type="number"
                    value={currentPrice}
                    onChange={(e) => setCurrentPrice(e.target.value)}
                    placeholder="129.99"
                    min="0"
                    step="0.01"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Currency</label>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                  >
                    {CURRENCY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Brand</label>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="e.g., Nike"
                  disabled={isAnalyzing}
                  className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Category</label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g., Running Shoes"
                  disabled={isAnalyzing}
                  className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Key Features</label>
                <input
                  type="text"
                  value={features}
                  onChange={(e) => setFeatures(e.target.value)}
                  placeholder="e.g., Air cushioning, Retro design, Leather upper"
                  disabled={isAnalyzing}
                  className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
                <p className="mt-1 text-xs text-muted-foreground">Comma-separated list</p>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
              <p className="font-medium text-destructive text-sm">Error</p>
              <p className="text-sm text-destructive/80 mt-1">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            {isAnalyzing ? (
              <button
                onClick={handleStop}
                className="flex-1 rounded-lg border border-destructive/50 bg-destructive/10 px-6 py-3 text-sm font-semibold text-destructive transition-all hover:bg-destructive/20"
              >
                ■ Stop Analysis
              </button>
            ) : (
              <button
                onClick={handleAnalyze}
                disabled={!canAnalyze}
                className="flex-1 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Analyze Market
              </button>
            )}
            {status !== "idle" && !isAnalyzing && (
              <button
                onClick={handleReset}
                className="rounded-lg border px-4 py-3 text-sm font-medium text-muted-foreground hover:bg-accent transition-colors"
              >
                Reset
              </button>
            )}
          </div>

          {/* Sources */}
          {sources.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-3">
                Sources ({sources.length})
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
                {sources.map((src, i) => (
                  <a
                    key={i}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg border bg-muted/30 p-3 hover:border-primary/50 transition-colors"
                  >
                    <p className="text-sm text-primary truncate">{src.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{src.url}</p>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Results */}
        <div className="space-y-6">
          {messages.length > 0 && (
            <div className="rounded-xl border bg-card p-4">
              <h3 className="text-sm font-semibold mb-4">Agent Activity</h3>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                {messages.map((msg, i) => {
                  const config = AGENT_CONFIG[msg.agent];
                  const thoughtLabel = msg.thought_type
                    ? THOUGHT_LABELS[msg.thought_type] || msg.thought_type
                    : null;
                  return (
                    <div
                      key={i}
                      className={`rounded-lg border ${config.borderColor} ${config.bgColor} p-3`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-bold ${config.color} uppercase tracking-wide`}>
                          {config.label}
                        </span>
                        {thoughtLabel && (
                          <span className="text-xs text-muted-foreground">• {thoughtLabel}</span>
                        )}
                        {msg.is_final && (
                          <span className="text-xs text-emerald-600 ml-auto">✓ Complete</span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </div>
                  );
                })}

                {isAnalyzing && activeAgent && (
                  <div
                    className={`rounded-lg border ${AGENT_CONFIG[activeAgent].borderColor} ${AGENT_CONFIG[activeAgent].bgColor} p-3 animate-pulse`}
                  >
                    <span className={`text-xs font-bold ${AGENT_CONFIG[activeAgent].color} uppercase tracking-wide`}>
                      {AGENT_CONFIG[activeAgent].label}
                    </span>
                    <p className="text-sm text-muted-foreground mt-1">
                      {AGENT_CONFIG[activeAgent].description}
                    </p>
                  </div>
                )}
                <div ref={streamEndRef} />
              </div>
            </div>
          )}

          {recommendation && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-6">
              <h3 className="text-sm font-semibold text-emerald-600 uppercase tracking-wide mb-4">
                Pricing Recommendation
              </h3>

              <div className="text-center mb-6">
                <p className="text-4xl font-bold">
                  ${recommendation.recommended_price.toFixed(2)}
                </p>
                <p className="text-sm text-muted-foreground mt-1">{recommendation.strategy}</p>
                {recommendation.price_change_percent !== 0 && (
                  <span
                    className={`inline-block mt-2 rounded-full px-3 py-1 text-xs font-medium ${
                      recommendation.price_change_percent > 0
                        ? "bg-emerald-500/20 text-emerald-600"
                        : "bg-red-500/20 text-red-600"
                    }`}
                  >
                    {recommendation.price_change_percent > 0 ? "+" : ""}
                    {recommendation.price_change_percent.toFixed(1)}%
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="rounded-lg bg-muted/50 p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Confidence</p>
                  <p className="text-lg font-semibold">
                    {(recommendation.confidence * 100).toFixed(0)}%
                  </p>
                  <div className="w-full bg-muted rounded-full h-1.5 mt-2">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${recommendation.confidence * 100}%` }}
                    />
                  </div>
                </div>
                <div className="rounded-lg bg-muted/50 p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Risk Level</p>
                  <p
                    className={`text-lg font-semibold capitalize ${
                      recommendation.risk_level === "low"
                        ? "text-emerald-600"
                        : recommendation.risk_level === "high"
                        ? "text-red-600"
                        : "text-amber-600"
                    }`}
                  >
                    {recommendation.risk_level}
                  </p>
                </div>
              </div>

              <div className="rounded-lg bg-muted/50 p-3 mb-4">
                <p className="text-xs text-muted-foreground mb-2">Suggested Range</p>
                <div className="flex items-center justify-between text-sm">
                  <span>${recommendation.price_range_low.toFixed(2)}</span>
                  <div className="flex-1 mx-3 h-1 bg-muted rounded-full relative">
                    <div
                      className="absolute h-3 w-3 bg-emerald-500 rounded-full top-1/2 -translate-y-1/2"
                      style={{
                        left: `${
                          recommendation.price_range_high - recommendation.price_range_low > 0
                            ? ((recommendation.recommended_price - recommendation.price_range_low) /
                                (recommendation.price_range_high - recommendation.price_range_low)) *
                              100
                            : 50
                        }%`,
                      }}
                    />
                  </div>
                  <span>${recommendation.price_range_high.toFixed(2)}</span>
                </div>
              </div>

              <div className="mb-4">
                <p className="text-xs text-muted-foreground mb-1">Reasoning</p>
                <p className="text-sm leading-relaxed">{recommendation.reasoning}</p>
              </div>

              {recommendation.key_factors.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Key Factors</p>
                  <div className="flex flex-wrap gap-2">
                    {recommendation.key_factors.map((factor, i) => (
                      <span key={i} className="rounded-full bg-muted border px-3 py-1 text-xs text-muted-foreground">
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {recommendation.sources_used > 0 && (
                <p className="text-xs text-muted-foreground mt-4 text-center">
                  Based on {recommendation.sources_used} live web sources
                </p>
              )}
            </div>
          )}

          {status === "idle" && (
            <div className="rounded-xl border bg-muted/30 p-8 text-center">
              <h3 className="font-medium text-muted-foreground mb-2">Ready to Analyze</h3>
              <p className="text-sm text-muted-foreground">
                Enter a product name to get AI-powered market intelligence with live web data and pricing recommendations.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}



