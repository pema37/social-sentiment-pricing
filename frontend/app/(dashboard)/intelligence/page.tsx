'use client';

// frontend/app/(dashboard)/intelligence/page.tsx
import { useState } from 'react';
import { SectionHeader } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  IEHealthBanner,
  ExperimentStatusCard,
  CalibrationChart,
  DriftAlertsList,
  CategoryPerformanceTable,
  OutcomeDashboard,
} from '@/components/features/intelligence';
import { useIEDashboard, useExperiments, useCalibration, useDriftAlerts, useCategoryPerformance } from '@/lib/hooks/use-intelligence';
import { useQueryClient } from '@tanstack/react-query';
import { intelligenceKeys } from '@/lib/hooks/use-intelligence';
import {
  RefreshCw,
  Brain,
} from 'lucide-react';

type TimeRange = 30 | 60 | 90;

export default function IntelligencePage() {
  const [timeRange, setTimeRange] = useState<TimeRange>(30);
  const queryClient = useQueryClient();

  // Combined dashboard call (health + top categories + drift + calibration)
  const { data: dashboard, isLoading: dashboardLoading, isFetching } = useIEDashboard(10);

  // Individual data for full components
  const { data: experiments, isLoading: experimentsLoading } = useExperiments();
  const { data: calibration, isLoading: calibrationLoading } = useCalibration();
  const { data: driftAlerts, isLoading: driftLoading } = useDriftAlerts();
  const { data: categories, isLoading: categoriesLoading } = useCategoryPerformance({
    min_recommendations: 5,
  });

  function handleRefresh() {
    queryClient.invalidateQueries({ queryKey: intelligenceKeys.all });
  }

  const timeRangeOptions: { value: TimeRange; label: string }[] = [
    { value: 30, label: '30 days' },
    { value: 60, label: '60 days' },
    { value: 90, label: '90 days' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <SectionHeader
        title="Intelligence Environment"
        description="How the pricing engine learns, experiments, and improves"
        action={
          <div className="flex items-center gap-3">
            {/* Time Range Selector */}
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {timeRangeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTimeRange(option.value)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    timeRange === option.value
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Refresh Button */}
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefresh}
              disabled={isFetching}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* Pipeline Health Banner */}
      {dashboard?.health && (
        <IEHealthBanner health={dashboard.health} isLoading={dashboardLoading} />
      )}
      {!dashboard?.health && dashboardLoading && (
        <IEHealthBanner
          health={{
            status: 'healthy',
            scoring_engine_healthy: true,
            experiment_manager_healthy: true,
            calibrator_healthy: true,
            context_injector_healthy: true,
            last_measurement_run: null,
            last_learning_cycle: null,
            last_bandit_update: null,
            last_calibration: null,
            active_experiments: 0,
            converged_categories: 0,
            total_categories: 0,
            drift_alerts_active: 0,
            pipeline_version: '',
          }}
          isLoading
        />
      )}

      {/* Drift Alerts — top placement for critical alerts */}
      <DriftAlertsList
        alerts={driftAlerts ?? dashboard?.active_drift_alerts ?? []}
        isLoading={driftLoading && dashboardLoading}
      />

      {/* Two-column: Experiments + Calibration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ExperimentStatusCard
          experiments={experiments ?? []}
          isLoading={experimentsLoading}
        />
        <CalibrationChart
          reports={calibration ?? (dashboard?.recent_calibration ? [dashboard.recent_calibration] : [])}
          isLoading={calibrationLoading && dashboardLoading}
        />
      </div>

      {/* Category Performance Table — full width */}
      <CategoryPerformanceTable
        categories={categories ?? dashboard?.top_categories ?? []}
        isLoading={categoriesLoading && dashboardLoading}
      />

      {/* Outcome Tracking — the feedback loop */}
      <OutcomeDashboard days={timeRange} />

      {/* Footer hint */}
      <div className="flex items-center justify-center gap-2 py-4 text-xs text-gray-400">
        <Brain className="w-3.5 h-3.5" />
        <span>
          The Intelligence Environment improves automatically as outcomes are measured.
          Target: Pearson r &gt; 0.7 by Month 12.
        </span>
      </div>
    </div>
  );
}


