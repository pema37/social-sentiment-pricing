"use client";

import { useState, useRef } from "react";
import Image from "next/image";
import {
  API_BASE,
  TREND_AGENTS,
  THOUGHT_LABELS,
  DIRECTION_COLORS,
  SIMULATE_OPTIONS,
  CATEGORY_OPTIONS
} from "./constants";
import type { TrendAgent, StreamEvent, SimulateTrend, Forecast, MarketData } from "./types";

interface AgentOutput {
  agent: TrendAgent;
  content: string;
  thoughtType?: string;
}

export default function MarketTrendsDemo() {
  const [product, setProduct] = useState("Wireless Earbuds");
  const [category, setCategory] = useState("electronics");
  const [simulateTrend, setSimulateTrend] = useState<SimulateTrend>("neutral");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [outputs, setOutputs] = useState<AgentOutput[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [activeAgent, setActiveAgent] = useState<TrendAgent | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const clearImage = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const runAnalysis = async () => {
    setIsRunning(true);
    setOutputs([]);
    setForecast(null);
    setMarketData(null);
    abortRef.current = new AbortController();

    try {
      let response: Response;

      if (imageFile) {
        const formData = new FormData();
        formData.append("product", product);
        formData.append("category", category);
        formData.append("simulate_trend", simulateTrend);
        formData.append("image", imageFile);

        response = await fetch(`${API_BASE}/trends-visual/analyze/stream`, {
          method: "POST",
          body: formData,
          signal: abortRef.current.signal
        });
      } else {
        const params = new URLSearchParams({
          product,
          category,
          simulate_trend: simulateTrend
        });
        response = await fetch(`${API_BASE}/trends-visual/analyze/stream?${params}`, {
          signal: abortRef.current.signal
        });
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("No reader");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          const event: StreamEvent = JSON.parse(line.slice(6));
          
          if (event.done) {
            if (event.market_data) setMarketData(event.market_data);
            break;
          }
          if (event.error) throw new Error(event.error);

          if (event.agent && event.content) {
            setActiveAgent(event.agent as TrendAgent);
            setOutputs(prev => [...prev, {
              agent: event.agent as TrendAgent,
              content: event.content!,
              thoughtType: event.thought_type || undefined
            }]);
          }

          if (event.metadata?.forecast) {
            setForecast(event.metadata.forecast);
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
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Market Trends Visual</h1>
        <p className="text-gray-400 mb-8">AI-powered market trend analysis with multimodal support</p>

        {/* Controls */}
        <div className="bg-gray-900 rounded-lg p-6 mb-8">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Product Name</label>
              <input
                type="text"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2"
                disabled={isRunning}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2"
                disabled={isRunning}
              >
                {CATEGORY_OPTIONS.map(cat => (
                  <option key={cat} value={cat}>{cat.charAt(0).toUpperCase() + cat.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Simulate Trend</label>
              <select
                value={simulateTrend}
                onChange={(e) => setSimulateTrend(e.target.value as SimulateTrend)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2"
                disabled={isRunning}
              >
                {SIMULATE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Image Upload */}
          <div className="mb-4">
            <label className="block text-sm text-gray-400 mb-2">Trend Chart Image (optional)</label>
            <div className="flex gap-4 items-start">
              <div className="flex-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2 text-sm"
                  disabled={isRunning}
                />
                <p className="text-xs text-gray-500 mt-1">Upload Google Trends, sales charts, or any trend visualization</p>
              </div>
              {imagePreview && (
                <div className="relative h-20 w-20">
                  <Image
                    src={imagePreview}
                    alt="Preview"
                    fill
                    className="object-cover rounded border border-gray-700"
                  />
                  <button
                    onClick={clearImage}
                    className="absolute -top-2 -right-2 bg-red-600 rounded-full w-5 h-5 text-xs z-10"
                    disabled={isRunning}
                  >
                    X
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={isRunning ? stopAnalysis : runAnalysis}
              className={`px-6 py-2 rounded font-medium ${
                isRunning
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {isRunning ? "Stop" : "Analyze Trends"}
            </button>
          </div>
        </div>

        {/* Agent Cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {(Object.keys(TREND_AGENTS) as TrendAgent[]).map((key) => {
            const agent = TREND_AGENTS[key];
            const isActive = activeAgent === key;
            return (
              <div
                key={key}
                className={`p-4 rounded-lg border-2 transition-all ${
                  isActive
                    ? `border-${agent.color}-500 bg-${agent.color}-500/10`
                    : "border-gray-800 bg-gray-900"
                }`}
              >
                <div className="font-medium">{agent.name}</div>
                <div className="text-sm text-gray-500">{agent.description}</div>
              </div>
            );
          })}
        </div>

        {/* Forecast Result */}
        {forecast && (
          <div className={`mb-6 p-4 rounded-lg border bg-${DIRECTION_COLORS[forecast.direction] || 'gray'}-500/10 border-${DIRECTION_COLORS[forecast.direction] || 'gray'}-500`}>
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-sm text-gray-400">Direction</div>
                <div className={`text-lg font-bold text-${DIRECTION_COLORS[forecast.direction] || 'gray'}-400 uppercase`}>
                  {forecast.direction.replace("_", " ")}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Confidence</div>
                <div className="text-lg font-bold">{forecast.confidence}%</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Action</div>
                <div className="text-lg font-bold">{forecast.recommended_action}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Timeframe</div>
                <div className="text-lg font-bold">{forecast.timeframe}</div>
              </div>
            </div>
          </div>
        )}

        {/* Market Data Summary */}
        {marketData && (
          <div className="mb-6 p-4 rounded-lg bg-gray-900 border border-gray-800">
            <div className="text-sm text-gray-400 mb-2">Market Data Used</div>
            <div className="grid grid-cols-5 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Sentiment:</span>{" "}
                <span className="font-medium">{marketData.sentiment_score}</span>
              </div>
              <div>
                <span className="text-gray-500">Volume:</span>{" "}
                <span className="font-medium">{marketData.volume_24h.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-500">7d Change:</span>{" "}
                <span className={`font-medium ${marketData.price_change_7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {marketData.price_change_7d >= 0 ? '+' : ''}{marketData.price_change_7d}%
                </span>
              </div>
              <div>
                <span className="text-gray-500">Mentions:</span>{" "}
                <span className="font-medium">{marketData.social_mentions}</span>
              </div>
              <div>
                <span className="text-gray-500">Competition:</span>{" "}
                <span className="font-medium capitalize">{marketData.competitor_activity}</span>
              </div>
            </div>
          </div>
        )}

        {/* Output Stream */}
        <div className="bg-gray-900 rounded-lg p-6 min-h-100">
          <h2 className="text-lg font-semibold mb-4">Analysis Stream</h2>
          {outputs.length === 0 ? (
            <p className="text-gray-500">Run analysis to see market trend insights...</p>
          ) : (
            <div className="space-y-2 font-mono text-sm max-h-125 overflow-y-auto">
              {outputs.map((o, i) => {
                const agentInfo = TREND_AGENTS[o.agent];
                const thought = o.thoughtType ? THOUGHT_LABELS[o.thoughtType] : null;
                return (
                  <div key={i} className="flex gap-2">
                    <span className={`text-${agentInfo?.color || 'gray'}-400 font-semibold shrink-0`}>
                      [{agentInfo?.name.split(" ")[0] || o.agent}]
                    </span>
                    {thought && (
                      <span className={`text-${thought.color}-400 shrink-0`}>[{thought.label}]</span>
                    )}
                    <span className="text-gray-300">{o.content}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}



