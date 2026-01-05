// components/features/alerts/CrisisDetectionCard.tsx
'use client';

import { useState } from 'react';
import { 
  AlertTriangle, 
  RefreshCw, 
  Brain, 
  ChevronDown, 
  ChevronUp,
  ExternalLink 
} from 'lucide-react';
import Link from 'next/link';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api/client';

interface CrisisAlert {
  product_id: string;
  product_name: string;
  severity: 'critical' | 'warning' | 'watch';
  sentiment_drop: number;
  current_sentiment: number;
  previous_sentiment: number;
  period_hours: number;
  negative_mentions: number;
  sample_texts: string[];
  ai_summary: string;
  recommended_actions: string[];
  ai_powered: boolean;
}

interface CrisisDetectionResponse {
  crises_detected: number;
  alerts: CrisisAlert[];
  scan_period_hours: number;
  ai_powered: boolean;
}

const severityConfig = {
  critical: { 
    label: 'Critical', 
    bg: 'bg-red-50', 
    border: 'border-red-200',
    text: 'text-red-700',
    badge: 'bg-red-100 text-red-800',
    icon: 'text-red-500'
  },
  warning: { 
    label: 'Warning', 
    bg: 'bg-orange-50', 
    border: 'border-orange-200',
    text: 'text-orange-700',
    badge: 'bg-orange-100 text-orange-800',
    icon: 'text-orange-500'
  },
  watch: { 
    label: 'Watch', 
    bg: 'bg-yellow-50', 
    border: 'border-yellow-200',
    text: 'text-yellow-700',
    badge: 'bg-yellow-100 text-yellow-800',
    icon: 'text-yellow-500'
  },
};

function CrisisAlertItem({ alert }: { alert: CrisisAlert }) {
  const [expanded, setExpanded] = useState(false);
  const config = severityConfig[alert.severity];

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} p-4`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <AlertTriangle className={`h-5 w-5 mt-0.5 ${config.icon}`} />
          <div>
            <div className="flex items-center gap-2">
              <Link 
                href={`/products/${alert.product_id}`}
                className={`font-medium ${config.text} hover:underline`}
              >
                {alert.product_name}
              </Link>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${config.badge}`}>
                {config.label}
              </span>
            </div>
            <p className="text-sm text-gray-600 mt-1">{alert.ai_summary}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>Drop: {alert.sentiment_drop}%</span>
              <span>Mentions: {alert.negative_mentions}</span>
              <span>Period: {alert.period_hours}h</span>
            </div>
          </div>
        </div>
        
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 text-gray-400 hover:text-gray-600"
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200 space-y-4">
          {/* Sentiment Details */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Current Sentiment:</span>
              <span className={`ml-2 font-medium ${alert.current_sentiment < 0 ? 'text-red-600' : 'text-green-600'}`}>
                {(alert.current_sentiment ?? 0).toFixed(3)}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Previous:</span>
              <span className="ml-2 font-medium text-gray-700">
                {(alert.previous_sentiment ?? 0).toFixed(3)}
              </span>
            </div>
          </div>

          {/* Sample Texts */}
          {alert.sample_texts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase mb-2">Sample Feedback</p>
              <div className="space-y-2">
                {alert.sample_texts.slice(0, 3).map((text, i) => (
                  <p key={i} className="text-sm text-gray-600 italic bg-white p-2 rounded border">
                    &quot;{text}&quot;
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Actions */}
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase mb-2">Recommended Actions</p>
            <ul className="space-y-1">
              {alert.recommended_actions.map((action, i) => (
                <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  {action}
                </li>
              ))}
            </ul>
          </div>

          {/* View Product Link */}
          <Link
            href={`/products/${alert.product_id}`}
            className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
          >
            View Product <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      )}
    </div>
  );
}

export function CrisisDetectionCard() {
  const [data, setData] = useState<CrisisDetectionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hours, setHours] = useState(24);

  const runDetection = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await api.get<CrisisDetectionResponse>(
        `/api/v1/alerts/crisis-detection?hours=${hours}`
      );
      setData(result);
    } catch (err) {
      setError((err as Error).message || 'Failed to run crisis detection');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-100 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">AI Crisis Detection</h3>
            <p className="text-xs text-gray-500">Scan for sentiment drops across products</p>
          </div>
        </div>

        {data && (
          <button
            onClick={runDetection}
            disabled={isLoading}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      {!data && !isLoading && !error && (
        <div className="text-center py-6">
          <p className="text-gray-500 text-sm mb-4">
            Scan all products for significant sentiment drops
          </p>
          <div className="flex items-center justify-center gap-3 mb-4">
            <label className="text-sm text-gray-600">Time period:</label>
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
            >
              <option value={12}>12 hours</option>
              <option value={24}>24 hours</option>
              <option value={48}>48 hours</option>
              <option value={72}>72 hours</option>
              <option value={168}>7 days</option>
            </select>
          </div>
          <Button onClick={runDetection} disabled={isLoading}>
            <Brain className="h-4 w-4 mr-2" />
            Run Crisis Scan
          </Button>
        </div>
      )}

      {isLoading && (
        <div className="py-8 text-center">
          <RefreshCw className="h-8 w-8 text-red-500 animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Scanning products for sentiment crises...</p>
        </div>
      )}

      {error && (
        <div className="py-6 text-center">
          <p className="text-red-600 text-sm mb-3">{error}</p>
          <Button variant="secondary" onClick={runDetection}>
            Try Again
          </Button>
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-4">
          {/* Summary */}
          <div className={`p-4 rounded-lg ${data.crises_detected > 0 ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className={`font-medium ${data.crises_detected > 0 ? 'text-red-700' : 'text-green-700'}`}>
                  {data.crises_detected > 0 
                    ? `${data.crises_detected} potential ${data.crises_detected === 1 ? 'crisis' : 'crises'} detected`
                    : 'No crises detected'}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Scanned last {data.scan_period_hours} hours
                </p>
              </div>
              {data.ai_powered && (
                <div className="flex items-center gap-1 text-xs text-purple-600">
                  <Brain className="h-3 w-3" />
                  AI Powered
                </div>
              )}
            </div>
          </div>

          {/* Crisis Alerts */}
          {data.alerts.length > 0 && (
            <div className="space-y-3">
              {data.alerts.map((alert, i) => (
                <CrisisAlertItem key={`${alert.product_id}-${i}`} alert={alert} />
              ))}
            </div>
          )}

          {data.crises_detected === 0 && (
            <p className="text-center text-gray-500 text-sm py-4">
              All products have stable sentiment. Great news! 🎉
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

export default CrisisDetectionCard;
