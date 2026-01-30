"use client";

import { useState, useRef } from "react";
import Image from "next/image";
import { API_BASE, LAUNCH_AGENTS, THOUGHT_LABELS, THREAT_COLORS } from "./constants";
import type { LaunchAgent, StreamEvent, ThreatLevel } from "./types";

interface AgentOutput {
  agent: LaunchAgent;
  content: string;
  thoughtType?: string;
}

export default function LaunchDetectorDemo() {
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
      let response: Response;

      if (imageFile) {
        const formData = new FormData();
        formData.append("competitor", competitor);
        formData.append("your_product", yourProduct);
        formData.append("simulate_launch", String(simulateLaunch));
        formData.append("image", imageFile);

        response = await fetch(`${API_BASE}/launch/analyze/stream`, {
          method: "POST",
          body: formData,
          signal: abortRef.current.signal
        });
      } else {
        const url = `${API_BASE}/launch/analyze/stream?competitor=${encodeURIComponent(competitor)}&your_product=${encodeURIComponent(yourProduct)}&simulate_launch=${simulateLaunch}`;
        response = await fetch(url, { signal: abortRef.current.signal });
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
          if (event.done) break;
          if (event.error) throw new Error(event.error);

          if (event.agent && event.content) {
            setActiveAgent(event.agent);
            setOutputs(prev => [...prev, {
              agent: event.agent!,
              content: event.content!,
              thoughtType: event.thought_type || undefined
            }]);
          }

          if (event.metadata?.assessment) {
            const assessment = event.metadata.assessment as { threat_level?: ThreatLevel };
            if (assessment.threat_level) {
              setThreatLevel(assessment.threat_level);
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
        <h1 className="text-3xl font-bold mb-2">Launch Detector</h1>
        <p className="text-gray-400 mb-8">AI-powered competitor product launch detection</p>

        {/* Controls */}
        <div className="bg-gray-900 rounded-lg p-6 mb-8">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Competitor Name</label>
              <input
                type="text"
                value={competitor}
                onChange={(e) => setCompetitor(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2"
                disabled={isRunning}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Your Product</label>
              <input
                type="text"
                value={yourProduct}
                onChange={(e) => setYourProduct(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2"
                disabled={isRunning}
              />
            </div>
          </div>

          {/* Image Upload */}
          <div className="mb-4">
            <label className="block text-sm text-gray-400 mb-2">Product Screenshot (optional)</label>
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

          <div className="flex gap-4 items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={simulateLaunch}
                onChange={(e) => setSimulateLaunch(e.target.checked)}
                disabled={isRunning}
                className="w-4 h-4"
              />
              <span className="text-sm text-gray-400">Simulate Launch</span>
            </label>
            <div className="flex-1" />
            <button
              onClick={isRunning ? stopAnalysis : runAnalysis}
              className={`px-6 py-2 rounded font-medium ${
                isRunning
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {isRunning ? "Stop" : "Detect Launch"}
            </button>
          </div>
        </div>

        {/* Agent Cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {(Object.keys(LAUNCH_AGENTS) as LaunchAgent[]).map((key) => {
            const agent = LAUNCH_AGENTS[key];
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

        {/* Threat Level Badge */}
        {threatLevel && (
          <div className={`mb-4 p-4 rounded-lg border bg-${THREAT_COLORS[threatLevel]}-500/10 border-${THREAT_COLORS[threatLevel]}-500`}>
            <span className="text-sm text-gray-400">Threat Level: </span>
            <span className={`font-bold text-${THREAT_COLORS[threatLevel]}-400 uppercase`}>
              {threatLevel}
            </span>
          </div>
        )}

        {/* Output Stream */}
        <div className="bg-gray-900 rounded-lg p-6 min-h-100">
          <h2 className="text-lg font-semibold mb-4">Analysis Stream</h2>
          {outputs.length === 0 ? (
            <p className="text-gray-500">Run analysis to detect competitor launches...</p>
          ) : (
            <div className="space-y-2 font-mono text-sm">
              {outputs.map((o, i) => {
                const agentInfo = LAUNCH_AGENTS[o.agent];
                const thought = o.thoughtType ? THOUGHT_LABELS[o.thoughtType] : null;
                return (
                  <div key={i} className="flex gap-2">
                    <span className={`text-${agentInfo.color}-400 font-semibold`}>
                      [{agentInfo.name.split(" ")[0]}]
                    </span>
                    {thought && (
                      <span className={`text-${thought.color}-400`}>[{thought.label}]</span>
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


