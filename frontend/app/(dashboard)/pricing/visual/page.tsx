"use client";

import React, { useState } from "react";
import { Camera } from "lucide-react";
import { useProducts } from "@/lib/hooks/use-products";
import { AgentMessage, AgentKey, PricingRecommendation, AnalysisStatus } from "@/components/features/pricing/visual/types";
import { ScreenshotUploader } from "@/components/features/pricing/visual/ScreenshotUploader";
import { AgentStream } from "@/components/features/pricing/visual/AgentStream";
import { RecommendationCard } from "@/components/features/pricing/visual/RecommendationCard";

export default function VisualPricingPage() {
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [productName, setProductName] = useState("");
  const [productPrice, setProductPrice] = useState("");
  const [productCurrency, setProductCurrency] = useState("USD");
  const [productFeatures, setProductFeatures] = useState("");

  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentKey | null>(null);
  const [recommendation, setRecommendation] = useState<PricingRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch merchant's real products
  const { data: productsData, isLoading: productsLoading } = useProducts({
    page: 1,
    page_size: 100,
  });
  const products = productsData?.items ?? [];

  // When a product is selected pre-fill name and price
  const handleProductSelect = (productId: string) => {
    if (!productId) return;
    const selected = products.find((p) => p.id === productId);
    if (!selected) return;
    setProductName(selected.name ?? "");
    setProductPrice(
      String(selected.current_price ?? selected.base_price ?? "")
    );
  };

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

      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${baseUrl}/api/v1/visual-pricing/analyze`, {
        method: "POST",
        body: formData,
        credentials: "include",
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

              if (data.error) throw new Error(data.error);

              if (data.agent) {
                setActiveAgent(data.agent as AgentKey);
                setMessages((prev) => [...prev, data as AgentMessage]);

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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Camera className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Visual Pricing</h1>
          <p className="text-sm text-muted-foreground">
            Upload a competitor screenshot and get AI-powered pricing recommendations
          </p>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column - Input */}
        <div className="space-y-6">

          {/* Optional product pre-fill */}
          <div className="rounded-lg border bg-muted/30 p-4">
            <label className="block text-sm font-medium mb-2">
              Pre-fill from your catalog{" "}
              <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            {productsLoading ? (
              <div className="w-full rounded-lg border bg-background px-4 py-3 text-sm text-muted-foreground">
                Loading products...
              </div>
            ) : products.length === 0 ? (
              <div className="w-full rounded-lg border bg-background px-4 py-3 text-sm text-muted-foreground">
                No products found — sync your store first
              </div>
            ) : (
              <select
                onChange={(e) => handleProductSelect(e.target.value)}
                disabled={isAnalyzing}
                defaultValue=""
                className="w-full rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              >
                <option value="">— Select a product to pre-fill —</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.sku ? ` (${p.sku})` : ""}
                  </option>
                ))}
              </select>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Selecting a product fills in the name and price below automatically
            </p>
          </div>

          <div>
            <h2 className="text-base font-semibold mb-4">1. Upload Competitor Screenshot</h2>
            <ScreenshotUploader
              onFileSelect={setScreenshot}
              selectedFile={screenshot}
              onClear={() => setScreenshot(null)}
              disabled={isAnalyzing}
            />
          </div>

          <div>
            <h2 className="text-base font-semibold mb-4">2. Your Product Details</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Product Name <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g., Premium Wireless Headphones"
                  disabled={isAnalyzing}
                  className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Current Price <span className="text-destructive">*</span>
                  </label>
                  <input
                    type="number"
                    value={productPrice}
                    onChange={(e) => setProductPrice(e.target.value)}
                    placeholder="99.99"
                    min="0"
                    step="0.01"
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border bg-background px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Currency</label>
                  <select
                    value={productCurrency}
                    onChange={(e) => setProductCurrency(e.target.value)}
                    disabled={isAnalyzing}
                    className="w-full rounded-lg border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CAD">CAD ($)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Key Features <span className="text-muted-foreground">(optional)</span>
                </label>
                <input
                  type="text"
                  value={productFeatures}
                  onChange={(e) => setProductFeatures(e.target.value)}
                  placeholder="e.g., Noise canceling, 40hr battery, Premium sound"
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
            <button
              onClick={handleAnalyze}
              disabled={!canAnalyze}
              className="flex-1 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isAnalyzing ? "Analyzing..." : "Analyze & Get Pricing"}
            </button>
            {status !== "idle" && (
              <button
                onClick={handleReset}
                disabled={isAnalyzing}
                className="rounded-lg border px-4 py-3 text-sm font-medium text-muted-foreground hover:bg-accent transition-colors disabled:opacity-50"
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
            <div className="rounded-xl border bg-muted/30 p-8 text-center">
              <h3 className="font-medium text-muted-foreground mb-2">Ready to Analyze</h3>
              <p className="text-sm text-muted-foreground">
                Upload a competitor product screenshot and enter your product details to get
                AI-powered pricing recommendations.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


