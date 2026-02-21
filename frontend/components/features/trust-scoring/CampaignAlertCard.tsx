// frontend/components/features/trust-scoring/CampaignAlertCard.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { 
  AlertTriangle, 
  Users, 
  FileText, 
  Clock, 
  Copy,
  TrendingUp,
  Activity,
  ShieldAlert
} from 'lucide-react';
import type { CampaignDetectionResponse, CampaignSignal } from '@/types/trust-scoring';

interface CampaignAlertCardProps {
  data: CampaignDetectionResponse;
  className?: string;
}

function getSignalIcon(signalType: string) {
  if (signalType.includes('timing')) return Clock;
  if (signalType.includes('similarity') || signalType.includes('content')) return Copy;
  if (signalType.includes('author')) return Users;
  if (signalType.includes('sentiment')) return TrendingUp;
  if (signalType.includes('burst')) return Activity;
  return AlertTriangle;
}

function getSignalColor(strength: number): string {
  if (strength >= 0.7) return 'text-red-600';
  if (strength >= 0.5) return 'text-orange-600';
  return 'text-yellow-600';
}

function getSignalBgColor(strength: number): string {
  if (strength >= 0.7) return 'bg-red-50';
  if (strength >= 0.5) return 'bg-orange-50';
  return 'bg-yellow-50';
}

export function CampaignAlertCard({ data, className = '' }: CampaignAlertCardProps) {
  const { 
    is_campaign_detected, 
    campaign_confidence, 
    signals, 
    metrics,
    suspicious_author_count,
    suspicious_content_count,
  } = data;

  if (!is_campaign_detected) {
    return (
      <Card className={`p-6 ${className}`}>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-100 rounded-full">
            <ShieldAlert size={20} className="text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">No Campaign Detected</h3>
            <p className="text-sm text-gray-500">
              Analyzed {metrics.posts_analyzed} posts from {metrics.unique_authors} authors
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`p-6 border-red-200 bg-red-50/30 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-100 rounded-full">
            <AlertTriangle size={20} className="text-red-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-red-900">Campaign Detected</h3>
            <p className="text-sm text-red-700">
              Coordinated manipulation activity identified
            </p>
          </div>
        </div>
        <Badge variant="danger" className="text-sm">
          {Math.round(campaign_confidence * 100)}% Confidence
        </Badge>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-4 gap-4 mb-6 p-4 bg-white rounded-lg">
        <MetricItem
          icon={FileText}
          label="Posts Analyzed"
          value={metrics.posts_analyzed}
        />
        <MetricItem
          icon={Users}
          label="Unique Authors"
          value={metrics.unique_authors}
        />
        <MetricItem
          icon={Users}
          label="Suspicious Authors"
          value={suspicious_author_count}
          highlight={suspicious_author_count > 0}
        />
        <MetricItem
          icon={FileText}
          label="Suspicious Posts"
          value={suspicious_content_count}
          highlight={suspicious_content_count > 0}
        />
      </div>

      {/* Signals */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Detection Signals</h4>
        <div className="space-y-2">
          {signals.map((signal, index) => (
            <SignalItem key={index} signal={signal} />
          ))}
        </div>
      </div>

      {/* Recommendations */}
      <div className="mt-6 p-4 bg-white rounded-lg border border-red-200">
        <h4 className="text-sm font-medium text-gray-900 mb-2">Recommended Actions</h4>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• Review flagged accounts and content manually</li>
          <li>• Consider excluding suspicious mentions from sentiment analysis</li>
          <li>• Monitor for continued coordinated activity</li>
          <li>• Check if campaign is targeting specific products</li>
        </ul>
      </div>
    </Card>
  );
}

// Metric item component
interface MetricItemProps {
  icon: typeof FileText;
  label: string;
  value: number;
  highlight?: boolean;
}

function MetricItem({ icon: Icon, label, value, highlight = false }: MetricItemProps) {
  return (
    <div className="text-center">
      <div className={`inline-flex p-2 rounded-full mb-2 ${
        highlight ? 'bg-red-100' : 'bg-gray-100'
      }`}>
        <Icon size={16} className={highlight ? 'text-red-600' : 'text-gray-600'} />
      </div>
      <p className={`text-lg font-semibold ${highlight ? 'text-red-700' : 'text-gray-900'}`}>
        {value}
      </p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}

// Signal item component
interface SignalItemProps {
  signal: CampaignSignal;
}

function SignalItem({ signal }: SignalItemProps) {
  const Icon = getSignalIcon(signal.signal_type);
  const strengthPercent = Math.round(signal.strength * 100);

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${getSignalBgColor(signal.strength)}`}>
      <Icon size={18} className={getSignalColor(signal.strength)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <p className={`text-sm font-medium ${getSignalColor(signal.strength)}`}>
            {formatSignalType(signal.signal_type)}
          </p>
          <span className={`text-xs font-semibold ${getSignalColor(signal.strength)}`}>
            {strengthPercent}%
          </span>
        </div>
        <p className="text-xs text-gray-600">{signal.description}</p>
      </div>
    </div>
  );
}

function formatSignalType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// Compact alert banner version
interface CampaignAlertBannerProps {
  isDetected: boolean;
  confidence?: number;
  onViewDetails?: () => void;
  className?: string;
}

export function CampaignAlertBanner({ 
  isDetected, 
  confidence = 0,
  onViewDetails,
  className = '' 
}: CampaignAlertBannerProps) {
  if (!isDetected) return null;

  return (
    <div className={`flex items-center justify-between p-3 bg-red-100 border border-red-200 rounded-lg ${className}`}>
      <div className="flex items-center gap-2">
        <AlertTriangle size={18} className="text-red-600" />
        <span className="text-sm font-medium text-red-800">
          Manipulation campaign detected ({Math.round(confidence * 100)}% confidence)
        </span>
      </div>
      {onViewDetails && (
        <button
          onClick={onViewDetails}
          className="text-sm font-medium text-red-700 hover:text-red-900 underline"
        >
          View Details
        </button>
      )}
    </div>
  );
}

export default CampaignAlertCard;



