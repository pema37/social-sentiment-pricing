"use client";

/**
 * Visual Pricing Intelligence Demo
 *
 * Gemini API Developer Competition Entry - Public Demo Page
 * URL: /demo/visual-pricing
 */

import React, { useState } from "react";
import { AgentMessage, AgentKey, PricingRecommendation, AnalysisStatus } from "./types";
import { API_BASE } from "./constants";
import { ScreenshotUploader } from "./components/ScreenshotUploader";
import { AgentStream } from "./components/AgentStream";
import { RecommendationCard } from "./components/RecommendationCard";

export default function VisualPricingDemo() {
  // Form state
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [productName, setProductName] = useState("");
  const [productPrice, setProductPrice] = useState("");
  const [productCurrency, setProductCurrency] = useState("USD");
  const [productFeatures, setProductFeatures] = useState("");

  // Analysis state
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentKey | null>(null);
  const [recommendation, setRecommendation] = useState<PricingRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!screenshot || !productName || !productPrice) {
      setError("Please fill in all required fields");
      return;
    }

    setStatus("analyzing");
    setMessages([]);
    setActiveAgent(null);
    setRecommendation(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("screenshot", screenshot);
      formData.append("product_name", productName);
      formData.append("product_price", productPrice);
      formData.append("product_currency", productCurrency);
      formData.append("product_features", productFeatures);

      // FIX: API_BASE already includes /api/v1
      const response = await fetch(`${API_BASE}/visual-pricing/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
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

                // Extract recommendation from strategist's final message
                if (data.agent === "strategist" && data.is_final && data.metadata?.recommendation) {
                  const rec = data.metadata.recommendation;
                  setRecommendation({
                    ...rec,
                    // Ensure numeric types for frontend rendering
                    recommended_price: Number(rec.recommended_price),
                    confidence: Number(rec.confidence),
                    price_change_percent: Number(rec.price_change_percent),
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
      setError(err instanceof Error ? err.message : "Analysis failed");
      setStatus("error");
      setActiveAgent(null);
    }
  };

  const handleReset = () => {
    setScreenshot(null);
    setProductName("");
    setProductPrice("");
    setProductFeatures("");
    setStatus("idle");
    setMessages([]);
    setActiveAgent(null);
    setRecommendation(null);
    setError(null);
  };

  const isAnalyzing = status === "analyzing";
  const canAnalyze = screenshot && productName && productPrice && !isAnalyzing;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-5xl px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-bold text-xl">Visual Pricing Intelligence</h1>
              <p className="text-sm text-gray-400">Powered by Google Gemini Multi-Agent System</p>
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
          {/* Left Column - Input */}
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-4">1. Upload Competitor Screenshot</h2>
              <ScreenshotUploader
                onFileSelect={setScreenshot}
                selectedFile={screenshot}
                onClear={() => setScreenshot(null)}
                disabled={isAnalyzing}
              />
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-4">2. Your Product Details</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Product Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="e.g., Premium Wireless Headphones"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Current Price <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="number"
                      value={productPrice}
                      onChange={(e) => setProductPrice(e.target.value)}
                      placeholder="99.99"
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
                      value={productCurrency}
                      onChange={(e) => setProductCurrency(e.target.value)}
                      disabled={isAnalyzing}
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                    >
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                      <option value="CAD">CAD ($)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Key Features (optional)
                  </label>
                  <input
                    type="text"
                    value={productFeatures}
                    onChange={(e) => setProductFeatures(e.target.value)}
                    placeholder="e.g., Noise canceling, 40hr battery, Premium sound"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                  />
                  <p className="mt-1 text-xs text-gray-500">Comma-separated list</p>
                </div>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                <p className="font-medium text-red-400">Error</p>
                <p className="text-sm text-red-300/80">{error}</p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleAnalyze}
                disabled={!canAnalyze}
                className="flex-1 rounded-lg bg-linear-to-r from-blue-500 to-purple-500 px-6 py-3 font-semibold text-white transition-all hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAnalyzing ? "Analyzing..." : "Analyze & Get Pricing"}
              </button>
              {status !== "idle" && (
                <button
                  onClick={handleReset}
                  disabled={isAnalyzing}
                  className="rounded-lg border border-gray-700 px-4 py-3 font-medium text-gray-300 hover:bg-white/5 transition-colors disabled:opacity-50"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Right Column - Results */}
          <div className="space-y-6">
            <AgentStream messages={messages} activeAgent={activeAgent} />

            {recommendation && <RecommendationCard recommendation={recommendation} />}

            {status === "idle" && (
              <div className="rounded-xl border border-gray-800 bg-gray-900/30 p-8 text-center">
                <h3 className="font-medium text-gray-400 mb-2">Ready to Analyze</h3>
                <p className="text-sm text-gray-500">
                  Upload a competitor product screenshot and enter your product details to get AI-powered pricing recommendations.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-sm text-gray-500">
          <p>
            GetActualPrice.com | Google Gemini API Developer Competition • February 2026
          </p>
        </div>
      </main>
    </div>
  );
}


