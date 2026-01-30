'use client';

import { useState } from 'react';
import Link from 'next/link';
import { 
  Sparkles, 
  TrendingUp, 
  Rocket, 
  BarChart3,
  ArrowRight,
  Zap,
  Brain,
  Eye,
  Shield
} from 'lucide-react';

const features = [
  {
    id: 'visual-pricing',
    title: 'Visual Pricing Intelligence',
    description: 'Upload competitor screenshots → AI extracts prices, analyzes positioning, and recommends optimal pricing strategy.',
    icon: Eye,
    href: '/demo/visual-pricing',
    gradient: 'from-violet-500 to-purple-600',
    features: ['Screenshot Analysis', 'Price Extraction', 'Competitive Positioning'],
    geminiFeature: 'Gemini 3 Vision + Reasoning',
  },
  {
    id: 'crisis-detector',
    title: 'Crisis Detector',
    description: 'Real-time monitoring of social sentiment with multi-agent analysis to detect PR crises before they escalate.',
    icon: Shield,
    href: '/demo/crisis-detector',
    gradient: 'from-red-500 to-orange-600',
    features: ['Sentiment Monitoring', 'Early Warning', 'Response Suggestions'],
    geminiFeature: 'Gemini 3 Streaming + Agents',
  },
  {
    id: 'launch-detector',
    title: 'Launch Detector',
    description: 'Identify competitor product launches from social signals and news, with strategic response recommendations.',
    icon: Rocket,
    href: '/demo/launch-detector',
    gradient: 'from-blue-500 to-cyan-600',
    features: ['Launch Detection', 'Threat Assessment', 'Counter Strategy'],
    geminiFeature: 'Gemini 3 Multimodal Analysis',
  },
  {
    id: 'market-trends',
    title: 'Market Trends Visual',
    description: 'Three-agent system (Observer → Analyst → Forecaster) that thinks through market data in real-time.',
    icon: TrendingUp,
    href: '/demo/market-trends',
    gradient: 'from-emerald-500 to-teal-600',
    features: ['Multi-Agent Reasoning', 'Trend Forecasting', 'Visual Thinking'],
    geminiFeature: 'Gemini 3 Chain-of-Thought',
  },
];

export default function DemoIndexPage() {
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[128px] animate-pulse" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[128px] animate-pulse delay-1000" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-150 h-150 bg-linear-to-r from-violet-500/5 to-cyan-500/5 rounded-full blur-[100px]" />
        
        {/* Grid overlay */}
        <div 
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '50px 50px',
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10">
        {/* Hero Section */}
        <header className="pt-16 pb-12 px-6">
          <div className="max-w-6xl mx-auto text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-linear-to-r from-violet-500/20 to-blue-500/20 border border-violet-500/30 mb-8">
              <Sparkles className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium bg-linear-to-r from-violet-400 to-blue-400 bg-clip-text text-transparent">
                Gemini 3 Hackathon Submission
              </span>
            </div>

            {/* Title */}
            <h1 className="text-5xl md:text-7xl font-bold mb-6 tracking-tight">
              <span className="bg-linear-to-r from-white via-white to-gray-400 bg-clip-text text-transparent">
                Social Sentiment
              </span>
              <br />
              <span className="bg-linear-to-r from-violet-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Pricing
              </span>
            </h1>

            {/* Subtitle */}
            <p className="text-xl md:text-2xl text-gray-400 max-w-3xl mx-auto mb-8 leading-relaxed">
              AI-powered dynamic pricing that watches social sentiment, tracks competitors, 
              and automatically adjusts your prices in real-time.
            </p>

            {/* Powered by Gemini */}
            <div className="flex items-center justify-center gap-3 text-gray-500">
              <Brain className="w-5 h-5" />
              <span className="text-sm">Powered by</span>
              <span className="font-semibold text-transparent bg-linear-to-r from-blue-400 to-cyan-400 bg-clip-text">
                Google Gemini 3
              </span>
            </div>
          </div>
        </header>

        {/* Feature Cards Grid */}
        <section className="px-6 pb-20">
          <div className="max-w-6xl mx-auto">
            <div className="grid md:grid-cols-2 gap-6">
              {features.map((feature, index) => {
                const Icon = feature.icon;
                const isHovered = hoveredCard === feature.id;
                
                return (
                  <Link
                    key={feature.id}
                    href={feature.href}
                    className="group relative"
                    onMouseEnter={() => setHoveredCard(feature.id)}
                    onMouseLeave={() => setHoveredCard(null)}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <div className={`
                      relative overflow-hidden rounded-2xl p-8 h-full
                      bg-linear-to-br from-white/[0.07] to-white/2
                      border border-white/10
                      transition-all duration-500 ease-out
                      ${isHovered ? 'border-white/20 scale-[1.02] shadow-2xl' : ''}
                    `}>
                      {/* Gradient glow on hover */}
                      <div className={`
                        absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500
                        bg-linear-to-br ${feature.gradient}
                      `} style={{ opacity: isHovered ? 0.05 : 0 }} />
                      
                      {/* Icon */}
                      <div className={`
                        w-14 h-14 rounded-xl mb-6 flex items-center justify-center
                        bg-linear-to-br ${feature.gradient}
                        shadow-lg
                        transition-transform duration-300
                        ${isHovered ? 'scale-110' : ''}
                      `}>
                        <Icon className="w-7 h-7 text-white" />
                      </div>

                      {/* Content */}
                      <h3 className="text-2xl font-bold mb-3 text-white group-hover:text-white transition-colors">
                        {feature.title}
                      </h3>
                      
                      <p className="text-gray-400 mb-6 leading-relaxed">
                        {feature.description}
                      </p>

                      {/* Feature tags */}
                      <div className="flex flex-wrap gap-2 mb-6">
                        {feature.features.map((f) => (
                          <span 
                            key={f}
                            className="px-3 py-1 rounded-full text-xs font-medium bg-white/5 text-gray-300 border border-white/10"
                          >
                            {f}
                          </span>
                        ))}
                      </div>

                      {/* Gemini badge */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <Zap className="w-4 h-4 text-yellow-500" />
                          <span>{feature.geminiFeature}</span>
                        </div>
                        
                        <div className={`
                          flex items-center gap-1 text-sm font-medium
                          transition-all duration-300
                          ${isHovered ? 'text-white translate-x-0' : 'text-gray-500 -translate-x-2 opacity-0'}
                        `}>
                          <span>Try Demo</span>
                          <ArrowRight className="w-4 h-4" />
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        {/* Architecture Section */}
        <section className="px-6 pb-20">
          <div className="max-w-4xl mx-auto">
            <div className="rounded-2xl bg-linear-to-br from-white/5 to-transparent border border-white/10 p-8 md:p-12">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <BarChart3 className="w-6 h-6 text-blue-400" />
                How It Works
              </h2>
              
              <div className="space-y-4 text-gray-400">
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-400 font-bold text-sm shrink-0">1</div>
                  <p><strong className="text-white">Connect your store</strong> — Shopify, WooCommerce, or any e-commerce platform</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-sm shrink-0">2</div>
                  <p><strong className="text-white">AI monitors signals</strong> — Social sentiment, competitor prices, market trends</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold text-sm shrink-0">3</div>
                  <p><strong className="text-white">Get pricing recommendations</strong> — AI explains reasoning, you approve or auto-apply</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-sm shrink-0">4</div>
                  <p><strong className="text-white">Maximize revenue</strong> — 15-25% revenue increase with real-time optimization</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="px-6 pb-12">
          <div className="max-w-6xl mx-auto text-center">
            <p className="text-gray-600 text-sm">
              Built for the Gemini 3 Hackathon • February 2026
            </p>
            <div className="flex items-center justify-center gap-4 mt-4">
              <a 
                href="https://github.com/your-repo" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-white transition-colors text-sm"
              >
                GitHub Repository
              </a>
              <span className="text-gray-700">•</span>
              <a 
                href="https://actualprice.io" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-white transition-colors text-sm"
              >
                ActualPrice.io
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}



