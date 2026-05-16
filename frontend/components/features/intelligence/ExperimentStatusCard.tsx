'use client';

// frontend/components/features/intelligence/ExperimentStatusCard.tsx
import { useState } from 'react';
import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  FlaskConical,
  Trophy,
  ChevronDown,
  ChevronUp,
  Clock,
} from 'lucide-react';
import type { ExperimentStatus, ExperimentArmStatus } from '@/types/intelligence';

interface ExperimentStatusCardProps {
  experiments: ExperimentStatus[];
  isLoading?: boolean;
}

function ArmBar({ arm, maxPulls }: { arm: ExperimentArmStatus; maxPulls: number }) {
  const pct = maxPulls > 0 ? (arm.pulls / maxPulls) * 100 : 0;
  const rewardPct = arm.expected_reward * 100;

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Arm name + leader badge */}
      <div className="w-36 shrink-0 flex items-center gap-1.5">
        {arm.is_leader && <Trophy className="w-3.5 h-3.5 text-amber-500" />}
        <span className={`text-sm truncate ${arm.is_leader ? 'font-semibold text-gray-900' : 'text-gray-600'}`}>
          {arm.arm_name}
        </span>
      </div>

      {/* Progress bar */}
      <div className="flex-1 min-w-0">
        <div className="h-5 bg-gray-100 rounded-full overflow-hidden relative">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              arm.is_leader ? 'bg-green-500' : 'bg-blue-400'
            }`}
            style={{ width: `${Math.max(pct, 2)}%` }}
          />
          <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700">
            {rewardPct.toFixed(1)}% reward
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="w-24 shrink-0 text-right text-xs text-gray-500">
        <span className="font-medium text-gray-700">{arm.wins}</span>/{arm.pulls} wins
      </div>
    </div>
  );
}

function ExperimentRow({ experiment }: { experiment: ExperimentStatus }) {
  const [expanded, setExpanded] = useState(false);
  const maxPulls = Math.max(...experiment.arms.map((a) => a.pulls), 1);

  return (
    <div className="border-b border-gray-100 last:border-0">
      {/* Header row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between py-3 px-1 hover:bg-gray-50 rounded-lg transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <FlaskConical className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-900">
            {experiment.category_id}
          </span>
          {experiment.converged ? (
            <Badge variant="success">
              Converged → {experiment.converged_arm}
            </Badge>
          ) : (
            <Badge variant="info">
              Exploring ({experiment.arms.length} arms)
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-500">
            {experiment.total_pulls.toLocaleString()} pulls
          </span>
          {experiment.last_updated && (
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {new Date(experiment.last_updated).toLocaleDateString()}
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded arm details */}
      {expanded && (
        <div className="pb-4 px-1">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                Arm Performance
              </span>
              <span className="text-xs text-gray-400">
                Exploration rate: {(experiment.exploration_rate * 100).toFixed(0)}%
              </span>
            </div>
            {experiment.arms
              .sort((a, b) => b.expected_reward - a.expected_reward)
              .map((arm) => (
                <ArmBar key={arm.arm_name} arm={arm} maxPulls={maxPulls} />
              ))}
            {experiment.convergence_confidence !== null && (
              <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-gray-200">
                Convergence confidence:{' '}
                <span className="font-semibold">
                  {(experiment.convergence_confidence ?? 0).toFixed(1)}%
                </span>
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function ExperimentStatusCard({ experiments, isLoading }: ExperimentStatusCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardTitle>Experiments</CardTitle>
        <div className="mt-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      </Card>
    );
  }

  const active = experiments.filter((e) => !e.converged);
  const converged = experiments.filter((e) => e.converged);

  return (
    <Card>
      <div className="flex items-center justify-between mb-1">
        <CardTitle>Experiments</CardTitle>
        <div className="flex items-center gap-2">
          <Badge variant="info">{active.length} active</Badge>
          <Badge variant="success">{converged.length} converged</Badge>
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Thompson Sampling A/B tests by product category
      </p>

      {experiments.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">
          <FlaskConical className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          No active experiments. Experiments start automatically as recommendations accumulate.
        </div>
      ) : (
        <div>
          {[...active, ...converged].map((exp) => (
            <ExperimentRow key={exp.category_id} experiment={exp} />
          ))}
        </div>
      )}
    </Card>
  );
}


