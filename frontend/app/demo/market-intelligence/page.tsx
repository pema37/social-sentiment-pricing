"use client";

/**
 * Market Intelligence Demo
 *
 * DeveloperWeek 2026 Hackathon - You.com Challenge Track
 * URL: /demo/market-intelligence
 *
 * Multi-agent pipeline: Scout → Analyst → Strategist
 * Scout uses You.com APIs for live web data with citations.
 */

import React, { useState, useRef, useEffect } from "react";
import {
  AgentMessage,
  AgentKey,
  PricingRecommendation,
  SourceLink,
  AnalysisStatus,
} from "./types";
import { API_BASE, AGENT_CONFIG, THOUGHT_LABELS, CURRENCY_OPTIONS } from "./constants";

export default function MarketIntelligenceDemo() {
  // ─── Form state ───
  const [productName, setProductName] = useState("");
  const [currentPrice, setCurrentPrice] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [features, setFeatures] = useState("");

  // ─── Analysis state ───
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentKey | null>(null);
  const [recommendation, setRecommendation] = useState<PricingRecommendation | null>(null);
  const [sources, setSources] = useState<SourceLink[]>([]);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const streamEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll as events arrive
  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ─── Handlers ───

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

      const response = await fetch(`${API_BASE}/market-intelligence/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

              if (data.error) {
                throw new Error(data.error);
              }

              if (data.agent) {
                setActiveAgent(data.agent as AgentKey);
                setMessages((prev) => [...prev, data as AgentMessage]);

                // Extract sources from scout final event
                if (
                  data.agent === "scout" &&
                  data.is_final &&
                  data.metadata?.sources
                ) {
                  setSources(data.metadata.sources as SourceLink[]);
                }

                // Extract recommendation from strategist final event
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

  // ─── Render ───

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-5xl px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-bold text-xl">Market Intelligence</h1>
              <p className="text-sm text-gray-400">
                Powered by You.com Live Search + Google Gemini Multi-Agent System
              </p>
            </div>
            <a
              href="/demo"
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              ← Back to Demo Hub
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* ─── Left Column: Input Form ─── */}
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-4">Product Details</h2>
              <div className="space-y-4">
                {/* Product Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Product Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="e.g., Nike Air Max 90"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                </div>

                {/* Price + Currency */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Current Price
                    </label>
                    <input
                      type="number"
                      value={currentPrice}
                      onChange={(e) => setCurrentPrice(e.target.value)}
                      placeholder="129.99"
                      min="0"
                      step="0.01"
                      disabled={isAnalyzing}
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Currency
                    </label>
                    <select
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                      disabled={isAnalyzing}
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                    >
                      {CURRENCY_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Brand */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Brand
                  </label>
                  <input
                    type="text"
                    value={brand}
                    onChange={(e) => setBrand(e.target.value)}
                    placeholder="e.g., Nike"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                </div>

                {/* Category */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Category
                  </label>
                  <input
                    type="text"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="e.g., Running Shoes"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Enables market trend analysis for this category
                  </p>
                </div>

                {/* Features */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Key Features
                  </label>
                  <input
                    type="text"
                    value={features}
                    onChange={(e) => setFeatures(e.target.value)}
                    placeholder="e.g., Air cushioning, Retro design, Leather upper"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                  <p className="mt-1 text-xs text-gray-500">Comma-separated list</p>
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                <p className="font-medium text-red-400">Error</p>
                <p className="text-sm text-red-300/80">{error}</p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              {isAnalyzing ? (
                <button
                  onClick={handleStop}
                  className="flex-1 rounded-lg border border-red-500/50 bg-red-500/10 px-6 py-3 font-semibold text-red-400 transition-all hover:bg-red-500/20"
                >
                  ■ Stop Analysis
                </button>
              ) : (
                <button
                  onClick={handleAnalyze}
                  disabled={!canAnalyze}
                  className="flex-1 rounded-lg bg-linear-to-r from-blue-500 to-purple-500 px-6 py-3 font-semibold text-white transition-all hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Analyze Market
                </button>
              )}
              {status !== "idle" && !isAnalyzing && (
                <button
                  onClick={handleReset}
                  className="rounded-lg border border-gray-700 px-4 py-3 font-medium text-gray-300 hover:bg-white/5 transition-colors"
                >
                  Reset
                </button>
              )}
            </div>

            {/* Sources */}
            {sources.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-300 mb-3">
                  Sources ({sources.length})
                </h3>
                <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
                  {sources.map((src, i) => (
                    <a
                      key={i}
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block rounded-lg border border-gray-800 bg-gray-900/50 p-3 hover:border-gray-600 transition-colors"
                    >
                      <p className="text-sm text-blue-400 truncate">{src.title}</p>
                      <p className="text-xs text-gray-500 truncate">{src.url}</p>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ─── Right Column: Results ─── */}
          <div className="space-y-6">
            {/* Agent Stream */}
            {messages.length > 0 && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/30 p-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Agent Activity
                </h3>
                <div className="space-y-3 max-h-125 overflow-y-auto pr-2">
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
                          <span
                            className={`text-xs font-bold ${config.color} uppercase tracking-wide`}
                          >
                            {config.label}
                          </span>
                          {thoughtLabel && (
                            <span className="text-xs text-gray-500">
                              • {thoughtLabel}
                            </span>
                          )}
                          {msg.is_final && (
                            <span className="text-xs text-green-500 ml-auto">
                              ✓ Complete
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                          {msg.content}
                        </p>
                      </div>
                    );
                  })}

                  {/* Loading indicator */}
                  {isAnalyzing && activeAgent && (
                    <div
                      className={`rounded-lg border ${AGENT_CONFIG[activeAgent].borderColor} ${AGENT_CONFIG[activeAgent].bgColor} p-3 animate-pulse`}
                    >
                      <span
                        className={`text-xs font-bold ${AGENT_CONFIG[activeAgent].color} uppercase tracking-wide`}
                      >
                        {AGENT_CONFIG[activeAgent].label}
                      </span>
                      <p className="text-sm text-gray-500 mt-1">
                        {AGENT_CONFIG[activeAgent].description}
                      </p>
                    </div>
                  )}

                  <div ref={streamEndRef} />
                </div>
              </div>
            )}

            {/* Recommendation Card */}
            {recommendation && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-6">
                <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wide mb-4">
                  Pricing Recommendation
                </h3>

                {/* Price */}
                <div className="text-center mb-6">
                  <p className="text-4xl font-bold text-white">
                    ${recommendation.recommended_price.toFixed(2)}
                  </p>
                  <p className="text-sm text-gray-400 mt-1">
                    {recommendation.strategy}
                  </p>
                  {recommendation.price_change_percent !== 0 && (
                    <span
                      className={`inline-block mt-2 rounded-full px-3 py-1 text-xs font-medium ${
                        recommendation.price_change_percent > 0
                          ? "bg-green-500/20 text-green-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {recommendation.price_change_percent > 0 ? "+" : ""}
                      {recommendation.price_change_percent.toFixed(1)}%
                    </span>
                  )}
                </div>

                {/* Confidence & Risk */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="rounded-lg bg-gray-800/50 p-3 text-center">
                    <p className="text-xs text-gray-400 mb-1">Confidence</p>
                    <p className="text-lg font-semibold text-white">
                      {(recommendation.confidence * 100).toFixed(0)}%
                    </p>
                    <div className="w-full bg-gray-700 rounded-full h-1.5 mt-2">
                      <div
                        className="bg-emerald-500 h-1.5 rounded-full transition-all"
                        style={{ width: `${recommendation.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="rounded-lg bg-gray-800/50 p-3 text-center">
                    <p className="text-xs text-gray-400 mb-1">Risk Level</p>
                    <p
                      className={`text-lg font-semibold capitalize ${
                        recommendation.risk_level === "low"
                          ? "text-green-400"
                          : recommendation.risk_level === "high"
                          ? "text-red-400"
                          : "text-amber-400"
                      }`}
                    >
                      {recommendation.risk_level}
                    </p>
                  </div>
                </div>

                {/* Price Range */}
                <div className="rounded-lg bg-gray-800/50 p-3 mb-4">
                  <p className="text-xs text-gray-400 mb-2">Suggested Range</p>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-300">
                      ${recommendation.price_range_low.toFixed(2)}
                    </span>
                    <div className="flex-1 mx-3 h-1 bg-gray-700 rounded-full relative">
                      <div
                        className="absolute h-3 w-3 bg-emerald-500 rounded-full top-1/2 -translate-y-1/2"
                        style={{
                          left: `${
                            recommendation.price_range_high -
                              recommendation.price_range_low >
                            0
                              ? ((recommendation.recommended_price -
                                  recommendation.price_range_low) /
                                  (recommendation.price_range_high -
                                    recommendation.price_range_low)) *
                                100
                              : 50
                          }%`,
                        }}
                      />
                    </div>
                    <span className="text-gray-300">
                      ${recommendation.price_range_high.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Reasoning */}
                <div className="mb-4">
                  <p className="text-xs text-gray-400 mb-1">Reasoning</p>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {recommendation.reasoning}
                  </p>
                </div>

                {/* Key Factors */}
                {recommendation.key_factors.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 mb-2">Key Factors</p>
                    <div className="flex flex-wrap gap-2">
                      {recommendation.key_factors.map((factor, i) => (
                        <span
                          key={i}
                          className="rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-300"
                        >
                          {factor}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sources count */}
                {recommendation.sources_used > 0 && (
                  <p className="text-xs text-gray-500 mt-4 text-center">
                    Based on {recommendation.sources_used} live web sources via You.com
                  </p>
                )}
              </div>
            )}

            {/* Empty State */}
            {status === "idle" && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/30 p-8 text-center">
                <h3 className="font-medium text-gray-400 mb-2">Ready to Analyze</h3>
                <p className="text-sm text-gray-500">
                  Enter a product name to get AI-powered market intelligence
                  with live web data and pricing recommendations.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-sm text-gray-500">
          <p>
            GetActualPrice.com | DeveloperWeek 2026 • You.com Challenge Track
          </p>
        </div>
      </main>
    </div>
  );
}

