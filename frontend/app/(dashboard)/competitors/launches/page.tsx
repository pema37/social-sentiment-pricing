"use client";

import { useState, useRef } from "react";
import Image from "next/image";
import { Rocket } from "lucide-react";
import {
  LAUNCH_AGENTS,
  THOUGHT_LABELS,
  THREAT_STYLES,
} from "@/components/features/competitors/launches/constants";
import type {
  LaunchAgent,
  StreamEvent,
  ThreatLevel,
} from "@/components/features/competitors/launches/types";

interface AgentOutput {
  agent: LaunchAgent;
  content: string;
  thoughtType?: string;
}

export default function LaunchDetectorPage() {
  const [competitor, setCompetitor] = useState("Apple");
  const [yourProduct, setYourProduct] = useState("Galaxy S24");
  const [simulateLaunch, setSimulateLaunch] = useState(true);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [outputs, setOutputs] = useState<AgentOutput[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [activeAgent, setActiveAgent] = useState<LaunchAgent | null>(null);
  const [threatLevel, setThreatLevel] = useState<ThreatLevel | null>(null);
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
    setThreatLevel(null);
    abortRef.current = new AbortController();

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      let response: Response;

      if (imageFile) {
        const formData = new FormData();
        formData.append("competitor", competitor);
        formData.append("your_product", yourProduct);
        formData.append("simulate_launch", String(simulateLaunch));
        formData.append("image", imageFile);

        response = await fetch(`${baseUrl}/api/v1/launch/analyze/stream`, {
          method: "POST",
          body: formData,
          credentials: "include",
          signal: abortRef.current.signal,
        });
      } else {
        const url = `${baseUrl}/api/v1/launch/analyze/stream?competitor=${encodeURIComponent(competitor)}&your_product=${encodeURIComponent(yourProduct)}&simulate_launch=${simulateLaunch}`;
        response = await fetch(url, {
          credentials: "include",
          signal: abortRef.current.signal,
        });
      }

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

            if (event.metadata?.assessment) {
              const assessment = event.metadata.assessment as { threat_level?: ThreatLevel };
              if (assessment.threat_level) {
                setThreatLevel(assessment.threat_level);
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

  const threatStyle = threatLevel
    ? THREAT_STYLES[threatLevel] || THREAT_STYLES.medium
    : null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Rocket className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Launch Detector</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered competitor product launch detection
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="rounded-lg border bg-card p-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-2">Competitor Name</label>
            <input
              type="text"
              value={competitor}
              onChange={(e) => setCompetitor(e.target.value)}
              className="w-full rounded-lg border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              disabled={isRunning}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Your Product</label>
            <input
              type="text"
              value={yourProduct}
              onChange={(e) => setYourProduct(e.target.value)}
              className="w-full rounded-lg border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              disabled={isRunning}
            />
          </div>
        </div>

        {/* Image Upload */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            Product Screenshot{" "}
            <span className="text-muted-foreground font-normal">(optional)</span>
          </label>
          <div className="flex gap-4 items-start">
            <div className="flex-1">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                onChange={handleImageChange}
                className="w-full rounded-lg border bg-background px-4 py-2 text-sm text-muted-foreground disabled:opacity-50"
                disabled={isRunning}
              />
            </div>
            {imagePreview && (
              <div className="relative h-20 w-20 shrink-0">
                <Image
                  src={imagePreview}
                  alt="Preview"
                  fill
                  className="object-cover rounded border"
                  unoptimized
                />
                <button
                  onClick={clearImage}
                  className="absolute -top-2 -right-2 bg-destructive hover:bg-destructive/90 rounded-full w-5 h-5 text-xs text-white z-10 transition-colors"
                  disabled={isRunning}
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-4 items-center">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={simulateLaunch}
              onChange={(e) => setSimulateLaunch(e.target.checked)}
              disabled={isRunning}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm text-muted-foreground">Simulate Launch</span>
          </label>
          <div className="flex-1" />
          <button
            onClick={isRunning ? stopAnalysis : runAnalysis}
            className={`px-6 py-2 rounded-lg text-sm font-medium transition-colors ${
              isRunning
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            }`}
          >
            {isRunning ? "Stop" : "Detect Launch"}
          </button>
        </div>
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-3 gap-4">
        {(Object.keys(LAUNCH_AGENTS) as LaunchAgent[]).map((key) => {
          const agent = LAUNCH_AGENTS[key];
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

      {/* Threat Level Badge */}
      {threatLevel && threatStyle && (
        <div className={`p-4 rounded-lg border ${threatStyle.bg} ${threatStyle.border}`}>
          <span className="text-sm text-muted-foreground">Threat Level: </span>
          <span className={`font-bold ${threatStyle.text} uppercase`}>
            {threatLevel}
          </span>
        </div>
      )}

      {/* Output Stream */}
      <div className="rounded-lg border bg-card p-6 min-h-48">
        <h2 className="text-base font-semibold mb-4">Analysis Stream</h2>
        {outputs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Run analysis to detect competitor launches...
          </p>
        ) : (
          <div className="space-y-2 font-mono text-sm max-h-96 overflow-y-auto">
            {outputs.map((o, i) => {
              const agentInfo = LAUNCH_AGENTS[o.agent];
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



