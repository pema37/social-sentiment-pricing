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
  Shield,
  ExternalLink
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const features = [
  {
    id: 'visual-pricing',
    title: 'Visual Pricing Intelligence',
    description: 'Upload competitor screenshots — AI extracts prices, analyzes positioning, and recommends optimal pricing strategy.',
    icon: Eye,
    href: '/demo/visual-pricing',
    gradient: 'from-emerald-500 to-emerald-600',
    tags: ['Screenshot Analysis', 'Price Extraction', 'Competitive Positioning'],
    geminiFeature: 'Google Gemini Vision + Reasoning',
    hoverBorder: 'hover:border-emerald-500/50',
    hoverShadow: 'hover:shadow-[0_20px_50px_-12px_rgba(16,185,129,0.25)]',
    accentText: 'text-emerald-400',
  },
  {
    id: 'crisis-detector',
    title: 'Crisis Detector',
    description: 'Real-time monitoring of social sentiment with multi-agent analysis to detect PR crises before they escalate.',
    icon: Shield,
    href: '/demo/crisis-detector',
    gradient: 'from-red-500 to-red-600',
    tags: ['Sentiment Monitoring', 'Early Warning', 'Response Suggestions'],
    geminiFeature: 'Google Gemini Streaming + Agents',
    hoverBorder: 'hover:border-red-500/50',
    hoverShadow: 'hover:shadow-[0_20px_50px_-12px_rgba(239,68,68,0.25)]',
    accentText: 'text-red-400',
  },
  {
    id: 'launch-detector',
    title: 'Launch Detector',
    description: 'Identify competitor product launches from social signals and news, with strategic response recommendations.',
    icon: Rocket,
    href: '/demo/launch-detector',
    gradient: 'from-violet-500 to-violet-600',
    tags: ['Launch Detection', 'Threat Assessment', 'Counter Strategy'],
    geminiFeature: 'Google Gemini Search + Analysis',
    hoverBorder: 'hover:border-violet-500/50',
    hoverShadow: 'hover:shadow-[0_20px_50px_-12px_rgba(139,92,246,0.25)]',
    accentText: 'text-violet-400',
  },
  {
    id: 'market-trends',
    title: 'Market Trends',
    description: 'Three-agent system (Observer → Analyst → Forecaster) that thinks through market data in real-time.',
    icon: TrendingUp,
    href: '/demo/market-trends',
    gradient: 'from-amber-500 to-amber-600',
    tags: ['Multi-Agent Reasoning', 'Trend Forecasting', 'Visual Thinking'],
    geminiFeature: 'Google Gemini Grounding + Prediction',
    hoverBorder: 'hover:border-amber-500/50',
    hoverShadow: 'hover:shadow-[0_20px_50px_-12px_rgba(245,158,11,0.25)]',
    accentText: 'text-amber-400',
  },
];

const stats = [
  { value: '118+', label: 'API Endpoints' },
  { value: '4', label: 'AI Agents' },
  { value: '15-25%', label: 'Revenue Impact' },
  { value: '<2s', label: 'Analysis Time' },
];

/* ------------------------------------------------------------------ */
/*  Feature Card                                                       */
/* ------------------------------------------------------------------ */

function FeatureCard({ feature, index }: { feature: typeof features[number]; index: number }) {
  const [isHovered, setIsHovered] = useState(false);
  const Icon = feature.icon;

  return (
    <Link
      href={feature.href}
      className="group relative block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className={`
        relative overflow-hidden rounded-2xl p-8 h-full
        bg-[rgba(30,30,46,0.8)]
        border border-white/8
        transition-all duration-500 ease-out
        ${feature.hoverBorder} ${feature.hoverShadow}
        ${isHovered ? 'scale-[1.02] -translate-y-1' : ''}
      `}>
        {/* Gradient glow on hover */}
        <div
          className={`
            absolute inset-0 transition-opacity duration-500
            bg-linear-to-br ${feature.gradient}
          `}
          style={{ opacity: isHovered ? 0.06 : 0 }}
        />

        {/* Icon */}
        <div className={`
          relative w-13 h-13 rounded-[14px] mb-5 flex items-center justify-center
          bg-linear-to-br ${feature.gradient}
          shadow-lg transition-transform duration-300
          ${isHovered ? 'scale-110' : ''}
        `}>
          <Icon className="w-6 h-6 text-white" />
        </div>

        {/* Title */}
        <h3 className="relative text-[22px] font-bold mb-3 text-gray-100 tracking-tight">
          {feature.title}
        </h3>

        {/* Description — improved contrast */}
        <p className="relative text-[15px] text-[#B0B3C1] mb-5 leading-relaxed">
          {feature.description}
        </p>

        {/* Tags */}
        <div className="relative flex flex-wrap gap-2 mb-5">
          {feature.tags.map((tag) => (
            <span
              key={tag}
              className="px-3 py-1 rounded-full text-xs font-medium bg-white/6 text-[#D0D3DE] border border-white/8"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Gemini badge + Try Demo */}
        <div className="relative flex items-center justify-between border-t border-white/6 pt-4">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Zap className="w-4 h-4 text-yellow-500" />
            <span>{feature.geminiFeature}</span>
          </div>

          <div className={`
            flex items-center gap-1.5 text-sm font-semibold
            transition-all duration-300 ${feature.accentText}
            ${isHovered ? 'translate-x-0 opacity-100' : '-translate-x-2 opacity-0'}
          `}>
            <span>Try demo</span>
            <ArrowRight className="w-4 h-4" />
          </div>
        </div>
      </div>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function DemoIndexPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[128px] animate-pulse" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-[128px] animate-pulse delay-1000" />

        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '64px 64px',
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10">
        {/* ── Header ─────────────────────────────────────────── */}
        <nav className="px-6 py-6">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-[10px] bg-linear-to-br from-blue-600 to-blue-700 flex items-center justify-center text-base font-extrabold">
                A
              </div>
              <span className="text-xl font-bold tracking-tight">ActualPrice</span>
            </div>
            <Link
              href="/dashboard"
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-100 transition-colors"
            >
              Back to Dashboard
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          </div>
        </nav>

        {/* ── Hero Section ───────────────────────────────────── */}
        <header className="pt-10 pb-10 px-6">
          <div className="max-w-6xl mx-auto text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-blue-600/12 border border-blue-500/25 mb-10">
              <Sparkles className="w-4 h-4 text-blue-300" />
              <span className="text-sm font-medium text-blue-300">
                Gemini API Developer Competition Submission
              </span>
            </div>

            {/* Title */}
            <h1 className="text-5xl md:text-7xl font-extrabold mb-6 tracking-tighter leading-[1.1]">
              <span className="block text-gray-100">
                Actual
              </span>
              <span
                className="block"
                style={{
                  background: 'linear-gradient(135deg, #38BDF8, #2563EB, #818CF8)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                Price
              </span>
            </h1>

            {/* Subtitle — bumped to #C4C7D4 for WCAG AA on dark bg */}
            <p className="text-lg md:text-xl text-[#C4C7D4] max-w-155 mx-auto mb-8 leading-relaxed">
              AI-powered dynamic pricing that watches social sentiment, tracks competitors,
              and automatically adjusts your prices in real-time.
            </p>

            {/* Powered by */}
            <div className="flex items-center justify-center gap-2 text-gray-400 text-[15px]">
              <Brain className="w-5 h-5" />
              <span>Powered by</span>
              <span className="font-semibold text-blue-300">
                Google Gemini
              </span>
            </div>
          </div>
        </header>

        {/* ── Stats Row ──────────────────────────────────────── */}
        <section className="px-6 pb-10">
          <div className="max-w-3xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-px rounded-xl overflow-hidden bg-white/6">
            {stats.map((stat) => (
              <div key={stat.label} className="bg-[rgba(17,17,39,0.9)] px-5 py-5 text-center">
                <div className="text-2xl font-bold text-gray-100">{stat.value}</div>
                <div className="mt-1 text-[13px] font-medium text-[#8B8FA3]">{stat.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Directional CTA ────────────────────────────────── */}
        <div className="text-center pb-8">
          <p className="text-[13px] font-medium uppercase tracking-widest text-gray-500">
            Explore our AI agents
          </p>
          <div className="mt-2 text-xl text-gray-600 animate-bounce">↓</div>
        </div>

        {/* ── Feature Cards Grid ─────────────────────────────── */}
        <section className="px-6 pb-20">
          <div className="max-w-6xl mx-auto">
            <div className="grid md:grid-cols-2 gap-5">
              {features.map((feature, index) => (
                <FeatureCard key={feature.id} feature={feature} index={index} />
              ))}
            </div>
          </div>
        </section>

        {/* ── How It Works ───────────────────────────────────── */}
        <section className="px-6 pb-20">
          <div className="max-w-4xl mx-auto">
            <div className="rounded-2xl bg-linear-to-br from-white/5 to-transparent border border-white/10 p-8 md:p-12">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <BarChart3 className="w-6 h-6 text-blue-400" />
                How It Works
              </h2>

              <div className="space-y-4 text-gray-400">
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold text-sm shrink-0">1</div>
                  <p><strong className="text-white">Connect your store</strong> — Shopify, WooCommerce, or any e-commerce platform</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-sm shrink-0">2</div>
                  <p><strong className="text-white">AI monitors signals</strong> — Social sentiment, competitor prices, market trends</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-400 font-bold text-sm shrink-0">3</div>
                  <p><strong className="text-white">Get pricing recommendations</strong> — AI explains reasoning, you approve or auto-apply</p>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 font-bold text-sm shrink-0">4</div>
                  <p><strong className="text-white">Maximize revenue</strong> — 15-25% revenue increase with real-time optimization</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Footer ─────────────────────────────────────────── */}
        <footer className="px-6 pb-12 border-t border-white/6 pt-10">
          <div className="max-w-6xl mx-auto text-center">
            <p className="text-gray-500 text-sm">
              Built for the Google Gemini API Developer Competition • February 2026
            </p>
            <div className="flex items-center justify-center gap-4 mt-4">
              <a
                href="https://github.com/pema37/social-sentiment-pricing/tree/develop/frontend/app/demo"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-white transition-colors text-sm"
              >
                GitHub Repository
              </a>
              <span className="text-gray-700">•</span>
              <a
                href="https://getactualprice.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-white transition-colors text-sm"
              >
                GetActualPrice.com
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

