// frontend/app/(dashboard)/sentiment/trust/page.tsx

'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { 
  Shield, 
  Search, 
  RefreshCw, 
  AlertTriangle,
  User,
  FileText,
  TrendingUp,
  Info,
  ChevronLeft
} from 'lucide-react';
import Link from 'next/link';
import {
  useTrustScoringStats,
  useScoreAuthor,
  useAnalyzeContent,
  useQuickSpamCheck,
  useClearTrustCache,
} from '@/lib/hooks/use-trust-scoring';
import {
  TrustLevelBadge,
  TrustScoreGauge,
  RiskFlagList,
  AuthorTrustCard,
  ContentAnalysisCard,
  SpamCheckResult,
} from '@/components/features/trust-scoring';
import type { AuthorScoreResponse, ContentAnalysisResponse } from '@/types/trust-scoring';

export default function TrustScoringPage() {
  const [activeTab, setActiveTab] = useState<'author' | 'content' | 'spam'>('author');
  
  const { data: stats, isLoading: statsLoading } = useTrustScoringStats();
  const clearCache = useClearTrustCache();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link 
            href="/sentiment" 
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ChevronLeft size={20} className="text-gray-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Trust Scoring</h1>
            <p className="text-gray-500">Detect bots, spam, and manipulation</p>
          </div>
        </div>
        <Button
          variant="secondary"
          onClick={() => clearCache.mutate()}
          disabled={clearCache.isPending}
        >
          <RefreshCw size={16} className={clearCache.isPending ? 'animate-spin' : ''} />
          Clear Cache
        </Button>
      </div>

      {/* Info Card */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-blue-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-blue-800">
              Trust scoring helps filter out bot-generated content and manipulation campaigns 
              from your sentiment analysis. Authors are scored based on account age, followers, 
              posting patterns, and historical behavior.
            </p>
          </div>
        </div>
      </Card>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            label="Cache Size"
            value={stats.cache_stats.hash_cache_size}
            icon={FileText}
          />
          <StatCard
            label="Recent Content"
            value={stats.cache_stats.recent_content_size}
            icon={TrendingUp}
          />
          <StatCard
            label="Min Trust Threshold"
            value={`${Math.round(stats.config.min_trust_threshold * 100)}%`}
            icon={Shield}
          />
          <StatCard
            label="New Account Days"
            value={stats.config.new_account_threshold_days}
            icon={User}
          />
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b">
        <TabButton
          active={activeTab === 'author'}
          onClick={() => setActiveTab('author')}
          icon={User}
          label="Author Scoring"
        />
        <TabButton
          active={activeTab === 'content'}
          onClick={() => setActiveTab('content')}
          icon={FileText}
          label="Content Analysis"
        />
        <TabButton
          active={activeTab === 'spam'}
          onClick={() => setActiveTab('spam')}
          icon={AlertTriangle}
          label="Quick Spam Check"
        />
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'author' && <AuthorScoringTab />}
        {activeTab === 'content' && <ContentAnalysisTab />}
        {activeTab === 'spam' && <QuickSpamCheckTab />}
      </div>
    </div>
  );
}

// Stat Card Component
interface StatCardProps {
  label: string;
  value: string | number;
  icon: typeof Shield;
}

function StatCard({ label, value, icon: Icon }: StatCardProps) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gray-100 rounded-lg">
          <Icon size={18} className="text-gray-600" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </Card>
  );
}

// Tab Button Component
interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: typeof Shield;
  label: string;
}

function TabButton({ active, onClick, icon: Icon, label }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
        active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      <Icon size={18} />
      <span className="font-medium">{label}</span>
    </button>
  );
}

// Author Scoring Tab
function AuthorScoringTab() {
  const [authorId, setAuthorId] = useState('');
  const [username, setUsername] = useState('');
  const [source, setSource] = useState('twitter');
  const [followerCount, setFollowerCount] = useState('');
  const [result, setResult] = useState<AuthorScoreResponse | null>(null);

  const scoreAuthor = useScoreAuthor();

  const handleScore = () => {
    if (!authorId || !username) return;
    
    scoreAuthor.mutate({
      author_id: authorId,
      username,
      source,
      follower_count: followerCount ? parseInt(followerCount) : undefined,
    }, {
      onSuccess: (data) => setResult(data),
    });
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Input Form */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Score Author</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Author ID *
            </label>
            <Input
              value={authorId}
              onChange={(e) => setAuthorId(e.target.value)}
              placeholder="e.g., user_12345"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username *
            </label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g., johndoe"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Source
            </label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="twitter">Twitter</option>
              <option value="reddit">Reddit</option>
              <option value="facebook">Facebook</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Follower Count (optional)
            </label>
            <Input
              type="number"
              value={followerCount}
              onChange={(e) => setFollowerCount(e.target.value)}
              placeholder="e.g., 1000"
            />
          </div>
          <Button
            onClick={handleScore}
            disabled={!authorId || !username || scoreAuthor.isPending}
            className="w-full"
          >
            {scoreAuthor.isPending ? (
              <>
                <RefreshCw size={16} className="animate-spin mr-2" />
                Scoring...
              </>
            ) : (
              <>
                <Search size={16} className="mr-2" />
                Score Author
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Result */}
      <div>
        {result ? (
          <AuthorTrustCard data={result} />
        ) : (
          <Card className="p-6 flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <User size={48} className="mx-auto mb-3 opacity-30" />
              <p>Enter author details and click &quot;Score Author&quot;</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

// Content Analysis Tab
function ContentAnalysisTab() {
  const [contentId, setContentId] = useState('');
  const [text, setText] = useState('');
  const [authorUsername, setAuthorUsername] = useState('');
  const [result, setResult] = useState<ContentAnalysisResponse | null>(null);

  const analyzeContent = useAnalyzeContent();

  const handleAnalyze = () => {
    if (!text) return;
    
    analyzeContent.mutate({
      content_id: contentId || `content_${Date.now()}`,
      text,
      author_username: authorUsername || undefined,
    }, {
      onSuccess: (data) => setResult(data),
    });
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Input Form */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Analyze Content</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Content ID (optional)
            </label>
            <Input
              value={contentId}
              onChange={(e) => setContentId(e.target.value)}
              placeholder="e.g., post_abc123"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Content Text *
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the social media post content here..."
              rows={5}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Author Username (optional)
            </label>
            <Input
              value={authorUsername}
              onChange={(e) => setAuthorUsername(e.target.value)}
              placeholder="e.g., user123"
            />
          </div>
          <Button
            onClick={handleAnalyze}
            disabled={!text || analyzeContent.isPending}
            className="w-full"
          >
            {analyzeContent.isPending ? (
              <>
                <RefreshCw size={16} className="animate-spin mr-2" />
                Analyzing...
              </>
            ) : (
              <>
                <Search size={16} className="mr-2" />
                Analyze Content
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Result */}
      <div>
        {result ? (
          <ContentAnalysisCard data={result} content={text} />
        ) : (
          <Card className="p-6 flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <FileText size={48} className="mx-auto mb-3 opacity-30" />
              <p>Enter content and click &quot;Analyze Content&quot;</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

// Quick Spam Check Tab
function QuickSpamCheckTab() {
  const [text, setText] = useState('');
  const [username, setUsername] = useState('');
  const [result, setResult] = useState<{
    is_spam: boolean;
    spam_score: number;
    reasons: string[];
  } | null>(null);

  const checkSpam = useQuickSpamCheck();

  const handleCheck = () => {
    if (!text) return;
    
    checkSpam.mutate({
      text,
      username: username || undefined,
    }, {
      onSuccess: (data) => setResult(data),
    });
  };

  return (
    <div className="max-w-2xl mx-auto">
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Spam Check</h3>
        <p className="text-sm text-gray-500 mb-4">
          Quickly check if a piece of content is likely spam without full analysis.
        </p>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Content Text *
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste content to check for spam..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username (optional)
            </label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Helps detect bot-like usernames"
            />
          </div>
          <Button
            onClick={handleCheck}
            disabled={!text || checkSpam.isPending}
            className="w-full"
          >
            {checkSpam.isPending ? (
              <>
                <RefreshCw size={16} className="animate-spin mr-2" />
                Checking...
              </>
            ) : (
              <>
                <AlertTriangle size={16} className="mr-2" />
                Check for Spam
              </>
            )}
          </Button>
        </div>

        {/* Result */}
        {result && (
          <div className="mt-6">
            <SpamCheckResult
              isSpam={result.is_spam}
              spamScore={result.spam_score}
              reasons={result.reasons}
            />
          </div>
        )}
      </Card>
    </div>
  );
}


